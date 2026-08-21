import logging
from typing import Optional, List
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import json
import re
from datetime import datetime

logger = logging.getLogger("backend.tools.anti_ai_pen_tool")


class AntiAIPenInput(BaseModel):
    content: str = Field(description="Content to analyze for AI patterns")
    website_id: str = Field(description="Website ID")


class AntiAIPenTool(BaseTool):
    name: str = "anti_ai_pen"
    description: str = "Analyzes content for AI-sounding patterns and provides specific replacements. Removes overused AI phrases and makes content more human and professional."
    args_schema: type[BaseModel] = AntiAIPenInput
    _website_id: Optional[str] = None

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def _run(self, content: str, website_id: str = "") -> str:
        if not self._website_id:
            return json.dumps({"error": "website_id not set"})
        
        ai_patterns = {
            "filler_phrases": [
                r"\b(so|such)\b\s+(much|a lot|as much)",
                r"\b(and you know)\b",
                r"\b(like)\b(?=\s+(?:this|that|these|those))",
                r"\b(you know)\b",
                r"\b(kind of|sort of)\b",
                r"\b(in order to)\b",
                r"\b(due to the fact that)\b",
                r"\b(has the potential to)\b",
                r"\b(very|really)\b\s+(good|great|important|valuable|interesting|effective)",
            ],
            "passive_voice_issues": [
                r"\b(is|are|was|were)\s+(being|gone through|handled|managed|executed|implemented|developed|created|designed|analyzed)",
            ],
            "vague_phrases": [
                r"\b(in today's world)\b",
                r"\b(in today's digital age)\b",
                r"\b(a lot of\b)",
                r"\b(many different\b)",
                r"\b(a variety of\b)",
                r"\b(depending on the situation)\b",
            ],
            "excessive_hedging": [
                r"\b(can potentially|could potentially|might potentially)\b",
                r"\b(very likely|quite possibly|somewhat)\b",
            ]
        }
        
        replacements = {
            "so much": "significantly",
            "very good": "excellent",
            "very important": "crucial",
            "very valuable": "highly valuable",
            "a lot": "numerous",
            "in order to": "to",
            "due to the fact that": "because",
            "has the potential to": "can",
            "really": "truly",
            "really good": "excellent",
            "really important": "crucial",
            "sort of": "approximately",
            "kind of": "approximately",
            "some things": "aspects",
            "a number of": "several",
            "there are a number of": "there are several",
            "very big": "substantial",
            "really big": "substantial",
            "really small": "minimal",
            "very small": "minimal",
            "a lot of experience": "extensive experience",
            "lots of": "many",
            "basically": "",
            "actually": "",
            "just": "",
            "just a": "a",
        }
        
        issues = []
        fixed_content = content
        
        for category, patterns in ai_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    issues.append({
                        "type": category,
                        "pattern": match.group(0),
                        "position": match.start(),
                        "severity": "medium" if category in ["filler_phrases", "vague_phrases"] else "high"
                    })
        
        for old, new in replacements.items():
            fixed_content = re.sub(rf'\b{re.escape(old)}\b', new, fixed_content, flags=re.IGNORECASE)
        
        fixed_content = re.sub(r'\b(\w+)/(\w+)\b', r'\1 and \2', fixed_content)
        fixed_content = re.sub(r'\b(\w+)-like\b', r'\1-like', fixed_content)
        
        issues.extend(self._find_excess_punctuation(fixed_content))
        issues.extend(self._find_sentence_length_issues(fixed_content))
        
        result = {
            "original_length": len(content),
            "fixed_length": len(fixed_content),
            "issues_found": len(issues),
            "issues": issues[:25],
            "fixed_content": fixed_content[:5000],
            "confidence_score": max(0, 100 - len(issues) * 5),
            "recommendations": self._generate_recommendations(len(issues))
        }
        
        _log_proof(self._website_id, "anti_ai_pen", "analysis", "tool", f"issues={len(issues)}")
        return json.dumps(result, indent=2)
    
    def _find_excess_punctuation(self, content: str) -> List[Dict]:
        issues = []
        ellipsis_pattern = re.findall(r'\.{3,}', content)
        for elips in ellipsis_pattern:
            issues.append({
                "type": "punctuation",
                "pattern": elips,
                "message": "Replace ellipsis with period for professional tone",
                "severity": "low"
            })
        return issues
    
    def _find_sentence_length_issues(self, content: str) -> List[Dict]:
        issues = []
        sentences = re.split(r'[.!?]+', content)
        long_sentences = []
        
        for sent in sentences:
            words = sent.split()
            if len(words) > 35:
                long_sentences.append({
                    "length": len(words),
                    "text": sent.strip()[:100]
                })
        
        if long_sentences:
            issues.append({
                "type": "sentence_length",
                "message": f"Found {len(long_sentences)} sentences over 35 words",
                "samples": long_sentences[:3],
                "severity": "medium"
            })
        
        return issues
    
    def _generate_recommendations(self, issue_count: int) -> List[str]:
        recommendations = [
            "Replace filler words with precise terminology",
            "Use active voice instead of passive constructions",
            "Start sentences with strong action verbs",
            "Remove 'like', 'you know', 'so much' - be direct",
            "Vary sentence length for rhythm"
        ]
        
        if issue_count > 20:
            recommendations.insert(0, "Content has many AI patterns - consider substantial rewrite")
        
        return recommendations


def _log_proof(website_id: str, agent: str, tool: str, real_api: str, action: str) -> None:
    try:
        from ...database import get_supabase
        get_supabase().table("tasks").insert({
            "website_id": website_id,
            "agent_name": agent,
            "action": f"proof:{agent}:{tool}:{action}",
            "status": "success",
            "result": json.dumps({"real_api_called": real_api}),
            "real_api_called": real_api,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass


class ProfessionalTonePreserver(BaseTool):
    name: str = "tone_preserver"
    description: str = "Ensures content maintains professional, expert tone while avoiding AI-sounding language patterns"
    
    def __init__(self):
        super().__init__()
        self.professional_replacements = {
            "utilize": "use",
            "implement": "apply",
            "facilitate": "help",
            "authenticate": "verify",
            "construct": "build",
            "augment": "enhance",
            "converge": "come together",
            "endeavor": "effort",
            "ensure compliance": "follow",
            "pursuant to": "according to",
        }
        
        self.exclusion_phrases = [
            "as a professional", "as an expert", "in my capacity as",
            "it is important to note", "it should be noted that",
            "please be advised that"
        ]
        
        self.preferred_openings = [
            "Here's how to approach",
            "The key to success is",
            "What sets us apart is",
            "The strategy involves",
            "Your path forward should include",
            "Critical steps include"
        ]
    
    def analyze_and_fix(self, content: str) -> dict:
        issues = []
        fixed = content
        
        for formal, casual in self.professional_replacements.items():
            if formal in fixed:
                issues.append({"type": "overly_corporate", "find": formal, "replace": casual})
                fixed = fixed.replace(formal, casual)
        
        for phrase in self.exclusion_phrases:
            if phrase.lower() in fixed.lower():
                issues.append({"type": "legalistic", "find": phrase, "replace": "note"})
                fixed = re.sub(re.escape(phrase), "Note that", fixed, flags=re.IGNORECASE)
        
        return {
            "issues": issues,
            "fixed_content": fixed,
            "improvement_score": len(issues)
        }
