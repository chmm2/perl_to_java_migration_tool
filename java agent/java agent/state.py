# state.py
"""
State management for the multi-agent Perl-to-Java conversion system.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class AgentState:
    """State object that flows through the conversion pipeline."""
    
    file_path: str = ""
    structured_data: Dict[str, Any] = field(default_factory=dict)
    java_code: str = ""
    errors: List[str] = field(default_factory=list)
    fix_attempts: int = 0
    final_code: str = ""
    success: bool = False
    perl_analysis: Dict[str, Any] = field(default_factory=dict)
    translation_notes: List[str] = field(default_factory=list)
    perl_content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert AgentState to dictionary for serialization."""
        return {
            'file_path': self.file_path,
            'structured_data': self.structured_data,
            'java_code': self.java_code,
            'errors': self.errors,
            'fix_attempts': self.fix_attempts,
            'final_code': self.final_code,
            'success': self.success,
            'perl_analysis': self.perl_analysis,
            'translation_notes': self.translation_notes,
            'perl_content': self.perl_content
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentState':
        """Create AgentState from dictionary."""
        return cls(**data)