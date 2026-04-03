from anthropic import Anthropic
from app.core.config import settings
from typing import Optional

class AIService:
    def __init__(self):
        if settings.CLAUDE_API_KEY:
            self.client = Anthropic(api_key=settings.CLAUDE_API_KEY)
        else:
            self.client = None
    
    async def generate_page(self, prompt: str) -> Optional[str]:
        """Generate HTML page using Claude API"""
        if not self.client:
            return None
        
        try:
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": f"""Generate a complete, professional HTML landing page based on this description:

{prompt}

Requirements:
- Complete HTML with inline CSS
- Modern, responsive design
- Professional and conversion-optimized
- Include meta tags
- Mobile-friendly
- No external dependencies

Return ONLY the HTML code, nothing else."""
                }]
            )
            
            return message.content[0].text
        except Exception as e:
            print(f"AI generation error: {str(e)}")
            return None

ai_service = AIService()