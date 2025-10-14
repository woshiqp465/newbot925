"""AI意图分析模块"""
import json
import re
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class AIAnalyzer:
    def __init__(self, claude_client):
        self.claude_client = claude_client
        self.model = "claude-sonnet-4-20250514"
    
    async def analyze_intent(self, user_input: str) -> Dict:
        prompt = f"""分析Telegram群组搜索需求，生成3-5个搜索建议。
用户输入："{user_input}"
可用命令：/search /text /human /topchat
返回JSON：{{"explanation":"说明","suggestions":[{{"command":"/text","keyword":"关键词","description":"描述","icon":"💬"}}]}}"""
        
        try:
            response = self.claude_client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            ai_response = response.content[0].text.strip()
            json_match = re.search(r'```json\s*(.*?)\s*```', ai_response, re.DOTALL)
            if json_match:
                ai_response = json_match.group(1)
            
            analysis = json.loads(ai_response)
            return self._validate(analysis, user_input)
        except Exception as e:
            logger.error(f"AI分析失败: {e}")
            return self._fallback(user_input)
    
    def _validate(self, analysis, user_input):
        if 'suggestions' not in analysis:
            raise ValueError("缺少suggestions")
        return analysis
    
    def _fallback(self, user_input):
        return {
            "explanation": f"为您搜索「{user_input}」",
            "suggestions": [
                {"command": "/search", "keyword": user_input, "description": f"按名称:{user_input}", "icon": "🔍"},
                {"command": "/text", "keyword": user_input, "description": f"按内容:{user_input}", "icon": "💬"},
                {"command": "/topchat", "keyword": "", "description": "浏览热门", "icon": "🔥"}
            ]
        }
