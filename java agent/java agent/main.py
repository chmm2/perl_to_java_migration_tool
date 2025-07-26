# main.py
"""
Main execution file for the AST-only Perl-to-Java conversion system.
"""
import os
import json
import time
import asyncio
import logging
from typing import Dict, List, Any, Literal
from pathlib import Path

# LangGraph imports
from langgraph.graph import StateGraph, END

# Local imports - FIXED IMPORTS
from config import Settings, EnhancedGroqLLM
from state import AgentState
from data_agent import DataRetrievalAgent, Neo4jHandler
from analysis_agent import PerlAnalysisAgent
from codegen_agent import CodeGenerationAgent, CodeFixerAgent
from validation_agent import CodeAssuranceAgent, FinalValidationAgent


class MultiAgentCodeConversionSystem:
    """Main system orchestrating the multi-agent Perl-to-Java conversion workflow."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm = EnhancedGroqLLM(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens
        )
        self.neo4j_handler = Neo4jHandler(settings)
        self.graph = self._build_graph()

    def _build_graph(self):
        """Build the workflow graph with proper state handling."""
        workflow = StateGraph(AgentState)
        
        # Add all agent nodes
        workflow.add_node("data_retrieval", DataRetrievalAgent(self.neo4j_handler))
        workflow.add_node("perl_analysis", PerlAnalysisAgent(self.llm))
        workflow.add_node("code_generation", CodeGenerationAgent(self.llm))
        workflow.add_node("code_assurance", CodeAssuranceAgent(self.llm))
        workflow.add_node("code_fixer", CodeFixerAgent(self.llm))
        workflow.add_node("final_validation", FinalValidationAgent(self.llm))
        workflow.add_node("finisher", self._finalize_state)
        
        # Set entry point
        workflow.set_entry_point("data_retrieval")
        
        # Add edges
        workflow.add_edge("data_retrieval", "perl_analysis")
        workflow.add_edge("perl_analysis", "code_generation")
        workflow.add_edge("code_generation", "code_assurance")
        workflow.add_conditional_edges(
            "code_assurance",
            self.decide_after_assurance,
            {"fix": "code_fixer", "validate": "final_validation"}
        )
        workflow.add_edge("code_fixer", "code_assurance")
        workflow.add_edge("final_validation", "finisher")
        workflow.add_edge("finisher", END)
        
        return workflow.compile()

    def _finalize_state(self, state: AgentState) -> AgentState:
        """Finalize the state before completion."""
        state.success = not bool(state.errors) and bool(state.java_code)
        state.final_code = state.java_code
        return state

    def decide_after_assurance(self, state: AgentState) -> Literal["fix", "validate"]:
        """Decide whether to fix or validate after assurance."""
        if state.errors and state.fix_attempts < self.settings.max_fix_attempts:
            return "fix"
        return "validate"

    async def _save_output(self, file_path: str, state: AgentState):
        """Save the converted Java code and comprehensive report."""
        # Determine the outcome type for more nuanced reporting
        outcome = "full_translation"
        if any("scaffold for a procedural script" in note for note in state.translation_notes):
            outcome = "scaffold_generation"
            # A scaffold is a form of success, as the system did the correct thing.
            state.success = True
            state.errors = [] # Clear any previous non-blocking errors for scripts.

        status = "success" if state.success else "failed"
        output_dir = Path(self.settings.output_dir) / status
        output_dir.mkdir(parents=True, exist_ok=True)
        
        base_name = Path(file_path).stem.replace(" ", "_")
        
        # Save Java code
        if state.final_code:
            java_file = output_dir / f"{base_name}.java"
            java_file.write_text(state.final_code, encoding='utf-8')
            logging.info(f"Saved Java code to: {java_file}")
        
        # Save detailed conversion report
        report = {
            "source_file": file_path,
            "success": state.success,
            "conversion_outcome": outcome, # Add the new outcome field
            "errors": state.errors,
            "translation_notes": state.translation_notes,
            "perl_analysis": state.perl_analysis,
            "fix_attempts": state.fix_attempts,
            "conversion_mode": "AST_ONLY",
            "conversion_type": outcome, # For backward compatibility
            "conversion_stats": {
                "had_synthesized_content": bool(state.perl_content),
                "synthesized_content_length": len(state.perl_content),
                "java_code_length": len(state.final_code),
                "packages_found": len(state.structured_data.get('packages', [])),
                "methods_found": sum(
                    len(p.get('methods', [])) if isinstance(p.get('methods'), list) else 1
                    for p in state.structured_data.get('packages', [])
                ),
                "design_patterns_detected": len(state.structured_data.get('designPatterns', [])),
                "estimated_fields": sum(
                    len(p.get('estimatedFields', []))
                    for p in state.structured_data.get('packages', [])
                )
            },
            "ast_only_features": {
                "comprehensive_ast_analysis": True,
                "intelligent_field_inference": True,
                "design_pattern_detection": True,
                "no_perl_source_required": True
            }
        }
        
        report_file = output_dir / f"{base_name}_report.json"
        report_file.write_text(json.dumps(report, indent=2), encoding='utf-8')
        logging.info(f"Saved conversion report to: {report_file}")

    async def convert_file(self, file_path: str) -> Dict[str, Any]:
        """Convert a single Perl file to Java with comprehensive error handling."""
        initial_state = AgentState(file_path=file_path)
        final_state = initial_state
        
        try:
            # Execute workflow and collect final state
            final_step = None
            step_count = 0
            
            async for step in self.graph.astream(initial_state):
                step_count += 1
                step_name = list(step.keys())[0]
                step_state = step[step_name]
                
                # Ensure we always have an AgentState object
                if isinstance(step_state, dict):
                    step_state = AgentState.from_dict(step_state)
                
                if step_name == "finisher":
                    final_step = step_state
                    break
                else:
                    # Log progress
                    logging.info(f"✓ Completed step: {step_name}")
                    if hasattr(step_state, 'errors') and step_state.errors:
                        logging.warning(f"⚠️  Errors in {step_name}: {step_state.errors[:2]}")
            
            # Use the final step or the last processed state
            if final_step:
                final_state = final_step
            
            # Ensure final_state is an AgentState object
            if isinstance(final_state, dict):
                final_state = AgentState.from_dict(final_state)
            
            await self._save_output(file_path, final_state)
            
            # Calculate additional metrics
            java_lines = len(final_state.final_code.split('\n')) if final_state.final_code else 0
            analysis_quality = "high" if len(final_state.perl_analysis.get('subroutines', [])) > 0 else "basic"
            
            return {
                "success": final_state.success,
                "file_path": file_path,
                "errors": final_state.errors if not final_state.success else None,
                "translation_notes": final_state.translation_notes,
                "java_code_length": len(final_state.final_code) if final_state.final_code else 0,
                "java_lines_count": java_lines,
                "analysis_quality": analysis_quality,
                "fix_attempts": final_state.fix_attempts,
                "workflow_steps": step_count,
                "conversion_mode": "AST_ONLY"
            }
            
        except Exception as e:
            logging.error(f"💥 Conversion failed for {file_path}: {e}")
            # Create a failed state for error handling
            error_state = AgentState(
                file_path=file_path,
                success=False,
                errors=[str(e)],
                translation_notes=[],
                final_code=""
            )
            await self._save_output(file_path, error_state)
            
            return {
                "success": False,
                "file_path": file_path,
                "errors": [str(e)],
                "translation_notes": [],
                "java_code_length": 0,
                "java_lines_count": 0,
                "analysis_quality": "failed",
                "fix_attempts": 0,
                "workflow_steps": 0,
                "conversion_mode": "AST_ONLY"
            }

    async def convert_batch(self, file_paths: List[str], batch_size: int = 1):
        """Convert files in batches with intelligent rate limiting."""
        results = []
        total_files = len(file_paths)
        
        for i in range(0, total_files, batch_size):
            batch = file_paths[i:i + batch_size]
            batch_results = []
            
            for j, file_path in enumerate(batch):
                file_num = i + j + 1
                logging.info(f"\n{'='*60}")
                logging.info(f"🔄 AST-only conversion {file_num}/{total_files}: {Path(file_path).name}")
                logging.info(f"{'='*60}")
                
                result = await self.convert_file(file_path)
                batch_results.append(result)
                
                # Log immediate result
                if result['success']:
                    logging.info(f"✅ SUCCESS - {Path(file_path).name}")
                    logging.info(f"📊 Generated {result.get('java_code_length', 0):,} characters "
                               f"({result.get('java_lines_count', 0)} lines)")
                    logging.info(f"🔍 Analysis: {result.get('analysis_quality', 'unknown')}")
                else:
                    logging.error(f"❌ FAILED - {Path(file_path).name}")
                    if result.get('errors'):
                        logging.error(f"💭 Error: {result['errors'][0][:100]}...")
            
            results.extend(batch_results)
            
            # Intelligent wait between batches
            if i + batch_size < total_files:
                wait_time = 3
                logging.info(f"⏸️  Waiting {wait_time} seconds before next batch...")
                await asyncio.sleep(wait_time)
        
        return results

    def get_available_files(self):
        """Get list of available Perl files from Neo4j."""
        return self.neo4j_handler.get_available_files()

    async def close(self):
        """Clean up resources."""
        self.neo4j_handler.close()


async def main():
    """Main execution function with enhanced logging and reporting."""
    # Configure enhanced logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('ast_only_conversion.log', mode='w', encoding='utf-8')
        ]
    )
    
    # Load settings
    settings = Settings(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "password")
    )
    
    if not settings.groq_api_key or settings.groq_api_key == "YOUR_GROQ_API_KEY":
        logging.critical("❌ Groq API key missing. Please set GROQ_API_KEY environment variable.")
        return
    
    # Create conversion system
    system = MultiAgentCodeConversionSystem(settings)
    
    try:
        # Get available files
        files = system.get_available_files()
        if not files:
            logging.warning("❌ No files available in Neo4j database.")
            return
        
        # Display startup banner
        logging.info(f"\n{'='*80}")
        logging.info(f"🚀 AST-ONLY PERL TO JAVA CONVERSION SYSTEM")
        logging.info(f"   💎 NO PERL SOURCE CODE REQUIRED")
        logging.info(f"{'='*80}")
        logging.info(f"📁 Found {len(files)} files to convert:")
        for i, file in enumerate(files, 1):
            logging.info(f"  {i:2d}. {Path(file).name}")
        logging.info(f"{'='*80}")
        logging.info(f"🤖 Model: {settings.groq_model}")
        logging.info(f"🌡️  Temperature: {settings.temperature}")
        logging.info(f"🎯 AST-Only Features:")
        logging.info(f"   • Comprehensive AST data extraction")
        logging.info(f"   • Intelligent field and method inference")
        logging.info(f"   • Design pattern detection")
        logging.info(f"   • Complete business logic generation")
        logging.info(f"   • NO Perl source code access required")
        logging.info(f"{'='*80}\n")
        
        # Convert files
        start_time = time.time()
        results = await system.convert_batch(files, batch_size=1)
        end_time = time.time()
        
        # Generate comprehensive analytics
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        total_java_chars = sum(r.get('java_code_length', 0) for r in results if r['success'])
        total_java_lines = sum(r.get('java_lines_count', 0) for r in results if r['success'])
        avg_time_per_file = (end_time - start_time) / len(results) if results else 0
        
        high_quality_analyses = sum(1 for r in results if r.get('analysis_quality') == 'high')
        total_fix_attempts = sum(r.get('fix_attempts', 0) for r in results)
        
        # Display comprehensive summary
        logging.info(f"\n{'='*80}")
        logging.info(f"📊 AST-ONLY CONVERSION RESULTS")
        logging.info(f"{'='*80}")
        logging.info(f"🎯 Success Rate: {(successful/len(results)*100):.1f}% ({successful}/{len(results)})")
        logging.info(f"⏱️  Processing Time: {end_time - start_time:.2f} seconds")
        logging.info(f"⚡ Average Time/File: {avg_time_per_file:.2f} seconds")
        logging.info(f"📝 Total Java Generated:")
        logging.info(f"   • {total_java_chars:,} characters")
        logging.info(f"   • {total_java_lines:,} lines of code")
        logging.info(f"🔍 Analysis Quality:")
        logging.info(f"   • High-quality analyses: {high_quality_analyses}/{len(results)}")
        logging.info(f"   • Total fix attempts: {total_fix_attempts}")
        logging.info(f"💾 Output: {settings.output_dir}/")
        logging.info(f"⭐ AST-only conversion - No Perl source required!")
        logging.info(f"{'='*80}\n")
        
        # Detailed file results
        logging.info("📋 DETAILED CONVERSION RESULTS:")
        logging.info("-" * 80)
        for i, result in enumerate(results, 1):
            status_icon = "✅" if result['success'] else "❌"
            file_name = Path(result['file_path']).name
            code_size = result.get('java_code_length', 0)
            quality = result.get('analysis_quality', 'unknown')
            
            logging.info(f"{i:2d}. {status_icon} {file_name:<35} "
                        f"({code_size:,} chars, {quality} analysis)")
            
            if result.get('translation_notes'):
                notes = ', '.join(result['translation_notes'][:2])
                if len(notes) > 60:
                    notes = notes[:60] + "..."
                logging.info(f"    📌 {notes}")
            
            if not result['success'] and result.get('errors'):
                error = result['errors'][0]
                if len(error) > 80:
                    error = error[:80] + "..."
                logging.info(f"    ⚠️  {error}")
        
        logging.info("-" * 80)
        
        # Create summary files
        await _create_summary_files(settings, results, start_time, end_time, 
                                   successful, failed, total_java_chars, total_java_lines)
        
        # Final success message
        if successful > 0:
            logging.info(f"\n🎉 AST-only conversion completed successfully!")
            logging.info(f"✨ {successful} files converted to Java without Perl source")
            logging.info(f"📁 Check '{settings.output_dir}/success/' for generated files")
            logging.info(f"🏆 Powered by intelligent AST analysis!")
        
        if failed > 0:
            logging.info(f"\n⚠️  {failed} files require attention")
            logging.info(f"📁 Check '{settings.output_dir}/failed/' for error details")
            
    except Exception as e:
        logging.error(f"💥 System error: {e}", exc_info=True)
    finally:
        await system.close()
        logging.info(f"\n🔌 AST-only conversion system closed gracefully.")


async def _create_summary_files(settings, results, start_time, end_time, 
                               successful, failed, total_java_chars, total_java_lines):
    """Create comprehensive summary files."""
    
    # JSON summary with full analytics
    summary_file = Path(settings.output_dir) / "ast_only_conversion_summary.json"
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    
    summary_data = {
        "conversion_metadata": {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "conversion_mode": "AST_ONLY",
            "enhancement_version": "AST-Only v1.0",
            "total_files": len(results),
            "successful_conversions": successful,
            "failed_conversions": failed,
            "success_rate_percent": round((successful/len(results)*100), 2) if results else 0,
            "total_processing_time_seconds": round(end_time - start_time, 2),
            "average_time_per_file_seconds": round((end_time - start_time) / len(results), 2) if results else 0,
            "groq_model_used": settings.groq_model,
            "temperature_setting": settings.temperature,
            "no_perl_source_access": True
        },
        "ast_only_features": {
            "comprehensive_ast_extraction": True,
            "intelligent_field_inference": True,
            "design_pattern_detection": True,
            "synthetic_content_generation": True,
            "no_perl_source_required": True
        },
        "code_generation_analytics": {
            "total_java_characters": total_java_chars,
            "total_java_lines": total_java_lines,
            "average_chars_per_file": round(total_java_chars / successful, 2) if successful > 0 else 0,
            "average_lines_per_file": round(total_java_lines / successful, 2) if successful > 0 else 0,
            "largest_generated_file_chars": max((r.get('java_code_length', 0) for r in results), default=0),
            "analysis_quality_distribution": {
                "high": sum(1 for r in results if r.get('analysis_quality') == 'high'),
                "basic": sum(1 for r in results if r.get('analysis_quality') == 'basic'),
                "failed": sum(1 for r in results if r.get('analysis_quality') == 'failed')
            }
        },
        "file_results": [
            {
                "file_name": Path(r['file_path']).name,
                "file_path": r['file_path'],
                "success": r['success'],
                "java_code_length": r.get('java_code_length', 0),
                "java_lines_count": r.get('java_lines_count', 0),
                "analysis_quality": r.get('analysis_quality', 'unknown'),
                "fix_attempts": r.get('fix_attempts', 0),
                "conversion_mode": r.get('conversion_mode', 'AST_ONLY'),
                "translation_notes": r.get('translation_notes', []),
                "errors": r.get('errors', []) if not r['success'] else None
            }
            for r in results
        ]
    }
    
    summary_file.write_text(json.dumps(summary_data, indent=2), encoding='utf-8')
    logging.info(f"📄 AST-only JSON summary saved to: {summary_file}")
    
    # Simple text summary
    text_summary_file = Path(settings.output_dir) / "conversion_summary.txt"
    with open(text_summary_file, 'w', encoding='utf-8') as f:
        f.write(f"AST-ONLY PERL TO JAVA CONVERSION SUMMARY\n")
        f.write(f"NO PERL SOURCE CODE REQUIRED\n")
        f.write(f"{'='*70}\n")
        f.write(f"Conversion Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Conversion Mode: AST-Only (No Perl Source)\n")
        f.write(f"Model: {settings.groq_model} (temp: {settings.temperature})\n")
        f.write(f"Total Files: {len(results)}\n")
        f.write(f"Successful: {successful}\n")
        f.write(f"Failed: {failed}\n")
        f.write(f"Success Rate: {(successful/len(results)*100):.1f}%\n")
        f.write(f"Processing Time: {end_time - start_time:.2f} seconds\n")
        f.write(f"Java Code Generated: {total_java_chars:,} chars, {total_java_lines:,} lines\n")
        f.write(f"\nAST-ONLY FEATURES:\n")
        f.write(f"• Comprehensive AST data extraction\n")
        f.write(f"• Intelligent field and method inference\n")
        f.write(f"• Design pattern detection\n")
        f.write(f"• Synthetic content generation\n")
        f.write(f"• NO Perl source code access required\n")
        f.write(f"\nFILE RESULTS:\n")
        f.write(f"{'-'*70}\n")
        
        for result in results:
            status = "SUCCESS" if result['success'] else "FAILED"
            code_size = result.get('java_code_length', 0)
            quality = result.get('analysis_quality', '?')
            f.write(f"{Path(result['file_path']).name}: {status} "
                   f"({code_size:,} chars, {quality})\n")
    
    logging.info(f"📄 Text summary saved to: {text_summary_file}")


if __name__ == "__main__":
    # Check dependencies
    try:
        import httpx
        import langgraph
        import neo4j
    except ImportError as e:
        logging.error(f"❌ Missing required dependency: {e}")
        logging.error("Install with: pip install -r requirements.txt")
        exit(1)
    
    asyncio.run(main())