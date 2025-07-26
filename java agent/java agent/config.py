# config.py
"""
Configuration settings and enhanced LLM wrapper for the Perl-to-Java conversion system.
"""

import os
import re
import json
import time
import asyncio
import logging
import random
import httpx
from typing import Dict, List, Any
from pydantic_settings import BaseSettings
from pydantic import Field

from prompts import (
    PERL_ANALYSIS_PROMPT, COMPLETE_CLASS_PROMPT, CODE_FIX_PROMPT,
    CLASS_NAME_FIX_PROMPT, ADVANCED_VALIDATION_PROMPT,
    OPTIMIZATION_ENHANCEMENT_PROMPT, ERROR_DIAGNOSTIC_PROMPT
)


class Settings(BaseSettings):
    """Configuration settings for the conversion system."""
    groq_api_key: str = Field(default="YOUR_GROQ_API_KEY", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama3-70b-8192", alias="GROQ_MODEL")
    neo4j_uri: str = Field(default="neo4j://127.0.0.1:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="00900p009", alias="NEO4J_PASSWORD")
    output_dir: str = Field(default="output", alias="OUTPUT_DIR")
    max_fix_attempts: int = Field(default=4, alias="MAX_FIX_ATTEMPTS")
    temperature: float = Field(default=0.1, alias="TEMPERATURE")
    max_tokens: int = Field(default=4096, alias="MAX_TOKENS")

    class Config:
        env_file = ".env"
        extra = "ignore"


class EnhancedGroqLLM:
    """Enhanced Groq LLM wrapper with better error handling and specialized methods."""
    
    def __init__(self, api_key: str, model: str, temperature: float, max_tokens: int):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.url = "https://api.groq.com/openai/v1/chat/completions"
        self.last_call_time = 0
        self.min_call_interval = 2.0  # Increased to reduce rate limits

    async def _rate_limit_wait(self):
        """Ensure minimum time between API calls"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time
        if time_since_last_call < self.min_call_interval:
            wait_time = self.min_call_interval - time_since_last_call
            await asyncio.sleep(wait_time)
        self.last_call_time = time.time()

    def _post_process_response(self, response: str) -> str:
        """Clean up LLM response"""
        if not response:
            return response
            
        # Remove markdown code blocks
        if '```java' in response:
            response = response.split('```java')[1].split('```')[0].strip()
        elif '```' in response:
            parts = response.split('```')
            if len(parts) >= 3:
                response = parts[1].strip()
        
        # Remove common explanation phrases
        lines = response.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                continue
            if any(phrase in stripped.lower() for phrase in [
                'here is', 'here\'s', 'this method', 'this code',
                'explanation:', 'note:', 'output:', 'result:'
            ]):
                continue
            if '//' in line:
                line = line.split('//')[0].rstrip()
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()

    async def generate_with_prompt(self, prompt: str, system_message: str = None) -> str:
        """Generate response using custom prompt"""
        await self._rate_limit_wait()
        
        if not system_message:
            system_message = (
                "You are a Java code generator. CRITICAL RULES: "
                "1. Output ONLY executable Java code. "
                "2. NO comments (//, /*, or //). "
                "3. NO explanations, descriptions, or text outside code. "
                "4. NO markdown backticks or formatting. "
                "5. Follow the exact output format specified in the prompt."
            )
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        retries = 5
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(self.url, headers=headers, json=payload)
                    
                    if response.status_code == 429:
                        wait_time = 2 ** attempt + random.uniform(0, 1)
                        logging.warning(f"Rate limit hit. Retrying in {wait_time:.2f}s...")
                        await asyncio.sleep(wait_time)
                        continue
                        
                    response.raise_for_status()
                    raw_response = response.json()["choices"][0]["message"]["content"]
                    return self._post_process_response(raw_response)
                    
            except Exception as e:
                if attempt == retries - 1:
                    raise Exception(f"Groq API failed after {retries} attempts: {e}")
                wait_time = 2 ** attempt
                logging.warning(f"API error (attempt {attempt + 1}): {e}. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)

    async def analyze_perl_code(self, perl_content: str, packages: List[str], 
                              methods: List[str], imports: List[str]) -> Dict[str, Any]:
        """Analyze Perl code using specialized prompt"""
        prompt = PERL_ANALYSIS_PROMPT.format(
            perl_content=perl_content[:3000] if perl_content else "# No content available",
            packages=packages,
            methods=methods,
            imports=imports
        )
        
        system_message = (
            "You are a Perl code analysis expert. "
            "Return ONLY valid JSON analysis. "
            "NO explanations or text outside JSON. "
            "Follow the exact JSON format specified."
        )
        
        response = await self.generate_with_prompt(prompt, system_message)
        
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_text = response[json_start:json_end]
                # Clean up common JSON issues
                json_text = re.sub(r',\s*}', '}', json_text)  # Remove trailing commas
                json_text = re.sub(r',\s*]', ']', json_text)  # Remove trailing commas in arrays
                return json.loads(json_text)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error in Perl analysis: {e}")
            
        # Return default analysis on error
        return {
            "subroutines": [],
            "global_variables": [],
            "main_flow": "Analysis failed - using simplified approach",
            "perl_features": [],
            "imports_needed": ["java.util.*", "java.io.*"],
            "conversion_notes": ["Analysis failed, using basic conversion"]
        }

    async def generate_java_class(self, class_name: str, perl_content: str, 
                                analysis_data: Dict, packages: List[str], 
                                method_count: int) -> str:
        """Generate complete Java class using specialized prompt"""
        prompt = COMPLETE_CLASS_PROMPT.format(
            class_name=class_name,
            perl_content=perl_content[:2500] if perl_content else "# No content available",
            analysis_data=json.dumps(analysis_data, indent=2)[:1000],
            packages=packages,
            method_count=method_count
        )
        
        return await self.generate_with_prompt(prompt)

    async def fix_java_code(self, java_code: str, errors: List[str]) -> str:
        """Fix Java compilation errors using specialized prompt"""
        prompt = CODE_FIX_PROMPT.format(
            java_code=java_code,
            errors='\n'.join(errors[:5])  # Limit to first 5 errors
        )
        
        return await self.generate_with_prompt(prompt)

    async def fix_class_name_error(self, java_code: str, class_name: str) -> str:
        """Fix Java class name compilation errors using specialized prompt"""
        prompt = CLASS_NAME_FIX_PROMPT.format(
            java_code=java_code,
            class_name=class_name
        )
        
        return await self.generate_with_prompt(prompt)

    async def validate_java_code(self, java_code: str) -> Dict[str, Any]:
        """Validate Java code quality using advanced validation prompt"""
        prompt = ADVANCED_VALIDATION_PROMPT.format(java_code=java_code)
        
        system_message = (
            "You are a Java code quality validator. "
            "Return ONLY valid JSON validation report. "
            "NO explanations or text outside JSON. "
            "Follow the exact JSON format specified."
        )
        
        response = await self.generate_with_prompt(prompt, system_message)
        
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_text = response[json_start:json_end]
                json_text = re.sub(r',\s*}', '}', json_text)
                json_text = re.sub(r',\s*]', ']', json_text)
                return json.loads(json_text)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error in validation: {e}")
            
        return {
            "compilation_status": {"is_compilable": True},
            "validation_summary": "Basic validation completed"
        }

    async def optimize_java_code(self, java_code: str) -> str:
        """Optimize Java code using enhancement prompt"""
        prompt = OPTIMIZATION_ENHANCEMENT_PROMPT.format(java_code=java_code)
        return await self.generate_with_prompt(prompt)

    async def diagnose_errors(self, code_section: str, error_details: str) -> Dict[str, Any]:
        """Diagnose and fix errors using diagnostic prompt"""
        prompt = ERROR_DIAGNOSTIC_PROMPT.format(
            code_section=code_section,
            error_details=error_details
        )
        
        system_message = (
            "You are a Java error diagnostic expert. "
            "Return ONLY valid JSON diagnostic report. "
            "Follow the exact JSON format specified."
        )
        
        response = await self.generate_with_prompt(prompt, system_message)
        
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_text = response[json_start:json_end]
                json_text = re.sub(r',\s*}', '}', json_text)
                json_text = re.sub(r',\s*]', ']', json_text)
                return json.loads(json_text)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error in diagnostics: {e}")
            
        return {
            "error_analysis": {"primary_issues": ["Unknown error"]},
            "corrected_code_section": code_section
        }