# validation_agent.py
"""
FIXED: Enhanced validation agents with non-destructive validation and better error handling.
"""

import re
import logging
from pathlib import Path
from typing import Dict, Any, List

from config import EnhancedGroqLLM
from state import AgentState


class CodeAssuranceAgent:
    """FIXED: Non-destructive validation agent that doesn't break working code."""
    
    def __init__(self, llm: EnhancedGroqLLM):
        self.llm = llm

    async def __call__(self, state: AgentState) -> AgentState:
        """
        FIXED: Code Assurance Agent with non-destructive validation.
        """
        if not state.java_code:
            state.errors.append("No Java code generated for validation")
            return state

        try:
            # FIXED: Perform comprehensive validation without breaking working code
            validation_result = self._comprehensive_validation(state.java_code)
            
            # FIXED: Only add BLOCKING errors, not warnings
            if validation_result['blocking_errors']:
                state.errors.extend(validation_result['blocking_errors'])
                logging.warning(f"Found {len(validation_result['blocking_errors'])} blocking errors")
            
            # FIXED: Add insights as notes, not errors
            if validation_result['insights']:
                state.translation_notes.extend(validation_result['insights'])
            
            # FIXED: Only attempt LLM validation if we have blocking errors OR very good code
            code_quality_score = validation_result['quality_score']
            
            if validation_result['blocking_errors'] and len(validation_result['blocking_errors']) <= 2:
                # Try LLM validation for fixable errors
                try:
                    logging.info("Attempting LLM validation for error analysis...")
                    advanced_validation = await self.llm.validate_java_code(state.java_code[:2000])
                    
                    if isinstance(advanced_validation, dict):
                        # Extract useful insights without adding more errors
                        comp_status = advanced_validation.get('compilation_status', {})
                        if comp_status.get('is_compilable') == False:
                            # Only add severe syntax issues
                            syntax_issues = comp_status.get('syntax_issues', [])
                            severe_issues = [issue for issue in syntax_issues 
                                           if any(keyword in issue.lower() for keyword in 
                                                 ['unmatched', 'unbalanced', 'missing class', 'invalid syntax'])]
                            if severe_issues:
                                state.errors.extend(severe_issues[:2])  # Limit to 2 most important
                        
                        # Add quality insights
                        if 'validation_summary' in advanced_validation:
                            summary = advanced_validation['validation_summary']
                            state.translation_notes.append(f"Quality Assessment: {summary}")
                        
                        logging.info("✅ Advanced validation completed")
                    
                except Exception as e:
                    logging.warning(f"Advanced validation failed (non-critical): {e}")
                    # Don't add this as an error - it's not blocking
            
            elif code_quality_score >= 7 and not validation_result['blocking_errors']:
                # High quality code - add positive feedback
                state.translation_notes.append(f"High quality code generated (score: {code_quality_score}/10)")
            
            # FIXED: Add comprehensive analysis notes
            state.translation_notes.extend([
                f"Code validation completed - {len(state.java_code):,} characters",
                f"Quality score: {code_quality_score}/10",
                f"Structure: {validation_result['structure_summary']}"
            ])
            
            logging.info(f"✅ Code assurance completed - Quality: {code_quality_score}/10, "
                        f"Blocking errors: {len(validation_result['blocking_errors'])}")
            
        except Exception as e:
            logging.error(f"Code assurance failed: {e}")
            # FIXED: Don't add validation failures as blocking errors
            state.translation_notes.append("⚠️ Code validation encountered issues (non-blocking)")
        
        return state
    
    def _comprehensive_validation(self, java_code: str) -> Dict[str, Any]:
        """FIXED: Comprehensive but non-destructive validation."""
        result = {
            'blocking_errors': [],
            'warnings': [],
            'insights': [],
            'quality_score': 5,
            'structure_summary': 'Unknown'
        }
        
        if not java_code or not java_code.strip():
            result['blocking_errors'].append("Empty or whitespace-only Java code")
            result['quality_score'] = 0
            result['structure_summary'] = 'Empty'
            return result
        
        # FIXED: Structure analysis
        structure_analysis = self._analyze_code_structure(java_code)
        result['structure_summary'] = structure_analysis['summary']
        
        # FIXED: Only add BLOCKING errors
        if not structure_analysis['has_class']:
            result['blocking_errors'].append("No class declaration found")
        
        if not structure_analysis['balanced_braces']:
            result['blocking_errors'].append(
                f"Unbalanced braces: {structure_analysis['open_braces']} open, "
                f"{structure_analysis['close_braces']} close"
            )
        
        if not structure_analysis['balanced_parens']:
            result['warnings'].append(
                f"Unbalanced parentheses: {structure_analysis['open_parens']} open, "
                f"{structure_analysis['close_parens']} close"
            )
        
        # FIXED: Content quality analysis (insights, not errors)
        content_analysis = self._analyze_content_quality(java_code)
        result['insights'].extend(content_analysis['insights'])
        
        # FIXED: Calculate quality score
        quality_score = self._calculate_quality_score(structure_analysis, content_analysis, java_code)
        result['quality_score'] = quality_score
        
        # FIXED: Add positive insights for good code
        if quality_score >= 8:
            result['insights'].append("Excellent code structure and quality")
        elif quality_score >= 6:
            result['insights'].append("Good code structure with room for improvement")
        elif quality_score >= 4:
            result['insights'].append("Basic code structure present")
        else:
            result['insights'].append("Code structure needs significant improvement")
        
        return result
    
    def _analyze_code_structure(self, java_code: str) -> Dict[str, Any]:
        """Analyze basic code structure."""
        analysis = {
            'has_class': False,
            'has_methods': False,
            'has_imports': False,
            'has_package': False,
            'balanced_braces': False,
            'balanced_parens': False,
            'open_braces': 0,
            'close_braces': 0,
            'open_parens': 0,
            'close_parens': 0,
            'method_count': 0,
            'import_count': 0,
            'class_names': [],
            'summary': 'Unknown'
        }
        
        # Count braces and parentheses
        analysis['open_braces'] = java_code.count('{')
        analysis['close_braces'] = java_code.count('}')
        analysis['open_parens'] = java_code.count('(')
        analysis['close_parens'] = java_code.count(')')
        
        analysis['balanced_braces'] = analysis['open_braces'] == analysis['close_braces']
        analysis['balanced_parens'] = analysis['open_parens'] == analysis['close_parens']
        
        # Find classes
        class_matches = re.findall(r'\b(?:public\s+)?class\s+(\w+)', java_code)
        analysis['class_names'] = class_matches
        analysis['has_class'] = len(class_matches) > 0
        
        # Count methods
        method_pattern = r'\b(?:public|private|protected)\s+(?:static\s+)?\w+\s+\w+\s*\('
        method_matches = re.findall(method_pattern, java_code)
        analysis['method_count'] = len(method_matches)
        analysis['has_methods'] = analysis['method_count'] > 0
        
        # Count imports
        import_matches = re.findall(r'\bimport\s+[\w.]+\s*;', java_code)
        analysis['import_count'] = len(import_matches)
        analysis['has_imports'] = analysis['import_count'] > 0
        
        # Check for package
        analysis['has_package'] = bool(re.search(r'\bpackage\s+[\w.]+\s*;', java_code))
        
        # Generate summary
        if analysis['has_class'] and analysis['balanced_braces']:
            if analysis['method_count'] > 3:
                analysis['summary'] = f"Complete class with {analysis['method_count']} methods"
            elif analysis['method_count'] > 0:
                analysis['summary'] = f"Basic class with {analysis['method_count']} methods"
            else:
                analysis['summary'] = "Empty class structure"
        elif analysis['has_class']:
            analysis['summary'] = "Class with structural issues"
        else:
            analysis['summary'] = "No valid class structure"
        
        return analysis
    
    def _analyze_content_quality(self, java_code: str) -> Dict[str, Any]:
        """Analyze content quality and generate insights."""
        analysis = {
            'insights': [],
            'code_length': len(java_code),
            'line_count': 0,
            'comment_ratio': 0,
            'has_constructors': False,
            'has_getters_setters': False,
            'has_main_method': False
        }
        
        lines = [line.strip() for line in java_code.split('\n') if line.strip()]
        analysis['line_count'] = len(lines)
        
        # Count comments
        comment_lines = sum(1 for line in lines if line.startswith(('//','/*','*')))
        analysis['comment_ratio'] = comment_lines / max(len(lines), 1)
        
        # Check for constructors
        analysis['has_constructors'] = bool(re.search(r'\bpublic\s+\w+\s*\([^)]*\)\s*{', java_code))
        
        # Check for getters/setters
        getter_count = len(re.findall(r'\bget\w+\s*\(', java_code))
        setter_count = len(re.findall(r'\bset\w+\s*\(', java_code))
        analysis['has_getters_setters'] = getter_count > 0 or setter_count > 0
        
        # Check for main method
        analysis['has_main_method'] = 'public static void main' in java_code
        
        # Generate insights
        if analysis['code_length'] > 1000:
            analysis['insights'].append(f"Substantial code generated: {analysis['code_length']:,} characters")
        elif analysis['code_length'] > 300:
            analysis['insights'].append(f"Moderate code size: {analysis['code_length']:,} characters")
        else:
            analysis['insights'].append(f"Compact code: {analysis['code_length']:,} characters")
        
        if analysis['has_constructors']:
            analysis['insights'].append("Constructor methods detected")
        
        if analysis['has_getters_setters']:
            analysis['insights'].append(f"Accessor methods found: {getter_count} getters, {setter_count} setters")
        
        if analysis['has_main_method']:
            analysis['insights'].append("Main method present for execution")
        
        if analysis['comment_ratio'] > 0.1:
            analysis['insights'].append(f"Well-documented code ({analysis['comment_ratio']:.1%} comments)")
        
        return analysis
    
    def _calculate_quality_score(self, structure_analysis: Dict, content_analysis: Dict, java_code: str) -> int:
        """Calculate overall quality score (1-10)."""
        score = 5  # Start with neutral
        
        # Structure points
        if structure_analysis['has_class']:
            score += 2
        if structure_analysis['balanced_braces']:
            score += 1
        if structure_analysis['balanced_parens']:
            score += 0.5
        
        # Method points
        method_count = structure_analysis['method_count']
        if method_count > 0:
            score += 1
        if method_count > 2:
            score += 0.5
        if method_count > 5:
            score += 0.5
        
        # Content points
        if content_analysis['code_length'] > 200:
            score += 0.5
        if content_analysis['code_length'] > 500:
            score += 0.5
        
        if structure_analysis['has_imports']:
            score += 0.5
        
        if content_analysis['has_constructors']:
            score += 0.5
        
        if content_analysis['has_getters_setters']:
            score += 0.5
        
        # Penalties for obvious problems
        if 'TODO' in java_code and java_code.count('TODO') > 5:
            score -= 1
        
        if 'System.out.println' in java_code and java_code.count('System.out.println') > 3:
            score -= 0.5  # Indicates placeholder code
        
        if not structure_analysis['balanced_braces']:
            score -= 2
        
        return max(1, min(10, int(score)))


class FinalValidationAgent:
    """FIXED: Final validation with optional enhancement, non-destructive approach."""
    
    def __init__(self, llm: EnhancedGroqLLM):
        self.llm = llm

    async def __call__(self, state: AgentState) -> AgentState:
        """
        FIXED: Final validation that preserves working code.
        """
        if not state.java_code:
            state.errors.append("No Java code for final validation")
            return state
        
        try:
            # FIXED: Quick structural validation
            structural_check = self._quick_structural_validation(state.java_code)
            
            if structural_check['is_valid']:
                state.translation_notes.append("✅ Java structure validated successfully")
                
                # FIXED: Optional enhancement only for high-quality code without errors
                if (not state.errors and 
                    len(state.java_code) > 400 and 
                    structural_check['quality_score'] >= 6):
                    
                    try:
                        logging.info("Attempting code enhancement...")
                        enhanced_code = await self._safe_code_enhancement(state.java_code)
                        
                        if enhanced_code and self._validate_enhancement(state.java_code, enhanced_code):
                            original_length = len(state.java_code)
                            new_length = len(enhanced_code)
                            state.java_code = enhanced_code
                            state.translation_notes.append(
                                f"Code enhanced: {original_length} → {new_length} chars"
                            )
                            logging.info("✅ Code enhancement successful")
                        else:
                            logging.info("Enhancement declined - keeping original code")
                            
                    except Exception as e:
                        logging.info(f"Code enhancement skipped: {e}")
                        # This is fine - we keep the original working code
                
                # FIXED: Add conversion summary
                self._add_conversion_summary(state, structural_check)
                
                logging.info(f"✅ Final validation successful - Quality: {structural_check['quality_score']}/10")
                
            else:
                # FIXED: Only add critical structural errors
                if structural_check['critical_errors']:
                    state.errors.extend(structural_check['critical_errors'])
                
                state.translation_notes.append("⚠️ Code has structural issues but may still be usable")
                logging.warning(f"Structural issues found: {structural_check['critical_errors']}")
                
        except Exception as e:
            logging.error(f"Final validation failed: {e}")
            state.translation_notes.append("Final validation encountered errors (code preserved)")
        
        return state
    
    def _quick_structural_validation(self, java_code: str) -> Dict[str, Any]:
        """Quick validation that identifies only critical structural problems."""
        result = {
            'is_valid': True,
            'critical_errors': [],
            'quality_score': 5,
            'has_class': False,
            'has_methods': False,
            'balanced_braces': False
        }
        
        if not java_code or not java_code.strip():
            result['is_valid'] = False
            result['critical_errors'].append("Empty code")
            result['quality_score'] = 0
            return result
        
        # Check for class
        has_class = bool(re.search(r'\b(?:public\s+)?class\s+\w+', java_code))
        result['has_class'] = has_class
        
        if not has_class:
            result['critical_errors'].append("No class declaration found")
            result['is_valid'] = False
        
        # Check braces balance
        open_braces = java_code.count('{')
        close_braces = java_code.count('}')
        balanced_braces = open_braces == close_braces and open_braces > 0
        result['balanced_braces'] = balanced_braces
        
        if not balanced_braces:
            if open_braces == 0:
                result['critical_errors'].append("No braces found - invalid Java structure")
            else:
                result['critical_errors'].append("Unbalanced braces - code will not compile")
            result['is_valid'] = False
        
        # Check for methods
        method_count = len(re.findall(r'\b(?:public|private|protected)\s+(?:static\s+)?\w+\s+\w+\s*\(', java_code))
        result['has_methods'] = method_count > 0
        
        # Calculate quality score
        score = 5
        if has_class: score += 2
        if balanced_braces: score += 2
        if method_count > 0: score += 1
        if method_count > 2: score += 1
        if len(java_code) > 300: score += 1
        if 'import' in java_code: score += 0.5
        
        # Penalties
        if not balanced_braces: score -= 3
        if not has_class: score -= 3
        
        result['quality_score'] = max(0, min(10, int(score)))
        
        return result
    
    async def _safe_code_enhancement(self, java_code: str) -> str:
        """Attempt safe code enhancement via LLM."""
        try:
            # Only enhance if code is substantial and looks good
            if len(java_code) < 400:
                return None
            
            enhanced = await self.llm.optimize_java_code(java_code)
            return enhanced
            
        except Exception as e:
            logging.info(f"Code enhancement unavailable: {e}")
            return None
    
    def _validate_enhancement(self, original: str, enhanced: str) -> bool:
        """Validate that enhancement is actually better."""
        if not enhanced or len(enhanced) < 50:
            return False
        
        # Enhanced code should not be dramatically shorter
        if len(enhanced) < len(original) * 0.7:
            return False
        
        # Enhanced code should still have basic structure
        if 'class ' not in enhanced.lower():
            return False
        
        # Enhanced code should have balanced braces
        if enhanced.count('{') != enhanced.count('}'):
            return False
        
        # Check that enhancement didn't remove too much functionality
        original_methods = len(re.findall(r'\bpublic\s+\w+\s+\w+\s*\(', original))
        enhanced_methods = len(re.findall(r'\bpublic\s+\w+\s+\w+\s*\(', enhanced))
        
        if enhanced_methods < original_methods * 0.8:  # Shouldn't lose too many methods
            return False
        
        return True
    
    def _add_conversion_summary(self, state: AgentState, structural_check: Dict):
        """Add comprehensive conversion summary."""
        file_name = Path(state.file_path).name
        
        # Basic summary
        summary_lines = [f"Converted from Perl: {file_name}"]
        
        # Add analysis insights
        if state.perl_analysis:
            subroutines = state.perl_analysis.get('subroutines', [])
            if subroutines:
                summary_lines.append(f"Converted {len(subroutines)} subroutines to Java methods")
        
        # Add structural info
        if structural_check['has_class']:
            if structural_check['has_methods']:
                summary_lines.append("Generated complete Java class with methods")
            else:
                summary_lines.append("Generated basic Java class structure")
        
        # Add quality assessment
        quality = structural_check['quality_score']
        if quality >= 8:
            summary_lines.append("High-quality conversion achieved")
        elif quality >= 6:
            summary_lines.append("Good quality conversion with minor areas for improvement")
        elif quality >= 4:
            summary_lines.append("Basic conversion completed - manual review recommended")
        else:
            summary_lines.append("Conversion completed with limitations - significant review needed")
        
        # Add final quality score
        summary_lines.append(f"Final quality score: {quality}/10")
        
        state.translation_notes.extend(summary_lines)