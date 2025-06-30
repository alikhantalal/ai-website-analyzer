from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
import aiohttp
import asyncio
import json
import re
from urllib.parse import urljoin, urlparse
import time
from bs4 import BeautifulSoup
import requests
from emergentintegrations.llm.chat import LlmChat, UserMessage
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch
from io import BytesIO
import base64
from fastapi.responses import StreamingResponse

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Models
class AnalysisRequest(BaseModel):
    url: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class AnalysisProgress(BaseModel):
    session_id: str
    progress: int
    status: str
    message: str

class AnalysisResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    url: str
    overall_score: int
    performance_score: int
    seo_score: int
    technical_score: int
    accessibility_score: int
    schema_faq_score: int
    analysis_data: Dict[str, Any]
    ai_insights: Dict[str, Any]
    schema_faq_analysis: Dict[str, Any]
    checkpoint_category: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

# In-memory progress tracking
analysis_progress = {}

# Analysis Engine
class WebsiteAnalyzer:
    def __init__(self):
        self.openai_api_key = os.environ.get('OPENAI_API_KEY')
        
    async def analyze_website(self, url: str, session_id: str):
        """Main analysis function"""
        try:
            # Initialize progress
            analysis_progress[session_id] = {
                "progress": 0,
                "status": "starting",
                "message": "Initializing analysis..."
            }
            
            # Step 1: Fetch website content
            await self.update_progress(session_id, 10, "fetching", "Fetching website content...")
            html_content, status_code, response_time = await self.fetch_website(url)
            
            if not html_content:
                raise HTTPException(status_code=400, detail="Could not fetch website content")
            
            # Step 2: Parse and extract data
            await self.update_progress(session_id, 30, "parsing", "Parsing website structure...")
            parsed_data = self.parse_html_content(html_content, url)
            
            # Step 3: Analyze performance
            await self.update_progress(session_id, 50, "analyzing", "Analyzing performance metrics...")
            performance_data = self.analyze_performance(parsed_data, response_time, len(html_content))
            
            # Step 4: Analyze SEO
            await self.update_progress(session_id, 70, "analyzing", "Analyzing SEO factors...")
            seo_data = self.analyze_seo(parsed_data)
            
            # Step 5: Technical health check
            await self.update_progress(session_id, 80, "analyzing", "Checking technical health...")
            technical_data = self.analyze_technical_health(parsed_data, url)
            
            # Step 6: Accessibility analysis
            await self.update_progress(session_id, 85, "analyzing", "Analyzing accessibility...")
            accessibility_data = self.analyze_accessibility(parsed_data)
            
            # Step 7: Schema and FAQ analysis
            await self.update_progress(session_id, 90, "analyzing", "Analyzing schema and FAQ structure...")
            schema_faq_data = self.analyze_schema_and_faq(parsed_data, html_content)
            
            # Step 8: Generate AI insights
            await self.update_progress(session_id, 95, "generating", "Generating AI insights...")
            ai_insights = await self.generate_ai_insights(parsed_data, performance_data, seo_data, technical_data, url)
            
            # Step 9: Calculate scores
            scores = self.calculate_scores(performance_data, seo_data, technical_data, accessibility_data, schema_faq_data)
            
            # Compile final result
            analysis_data = {
                "performance": performance_data,
                "seo": seo_data,
                "technical": technical_data,
                "accessibility": accessibility_data,
                "schema_faq": schema_faq_data,
                "parsed_content": parsed_data
            }
            
            result = AnalysisResult(
                session_id=session_id,
                url=url,
                overall_score=scores["overall"],
                performance_score=scores["performance"],
                seo_score=scores["seo"],
                technical_score=scores["technical"],
                accessibility_score=scores["accessibility"],
                schema_faq_score=scores["schema_faq"],
                analysis_data=analysis_data,
                ai_insights=ai_insights,
                schema_faq_analysis=schema_faq_data,
                checkpoint_category=schema_faq_data["checkpoint_category"],
                completed_at=datetime.utcnow()
            )
            
            # Save to database
            await db.analyses.insert_one(result.dict())
            
            # Final progress update
            await self.update_progress(session_id, 100, "completed", "Analysis completed!")
            
            return result
            
        except Exception as e:
            logger.error(f"Analysis failed for {url}: {str(e)}")
            analysis_progress[session_id] = {
                "progress": 0,
                "status": "error",
                "message": f"Analysis failed: {str(e)}"
            }
            raise HTTPException(status_code=500, detail=str(e))
    
    async def update_progress(self, session_id: str, progress: int, status: str, message: str):
        analysis_progress[session_id] = {
            "progress": progress,
            "status": status,
            "message": message
        }
        await asyncio.sleep(0.1)  # Small delay for realistic progress
    
    async def fetch_website(self, url: str):
        """Fetch website content with performance timing"""
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            start_time = time.time()
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }) as response:
                    html_content = await response.text()
                    response_time = time.time() - start_time
                    return html_content, response.status, response_time
                    
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {str(e)}")
            return None, None, None
    
    def parse_html_content(self, html_content: str, url: str):
        """Parse HTML and extract relevant data"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract meta information
        title = soup.find('title')
        title_text = title.get_text().strip() if title else ""
        
        meta_description = soup.find('meta', attrs={'name': 'description'})
        meta_description_text = meta_description.get('content', '') if meta_description else ""
        
        # Extract headings
        headings = {
            'h1': [h.get_text().strip() for h in soup.find_all('h1')],
            'h2': [h.get_text().strip() for h in soup.find_all('h2')],
            'h3': [h.get_text().strip() for h in soup.find_all('h3')],
            'h4': [h.get_text().strip() for h in soup.find_all('h4')],
            'h5': [h.get_text().strip() for h in soup.find_all('h5')],
            'h6': [h.get_text().strip() for h in soup.find_all('h6')]
        }
        
        # Extract links
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('http'):
                links.append({'url': href, 'text': link.get_text().strip(), 'external': True})
            elif href.startswith('/'):
                full_url = urljoin(url, href)
                links.append({'url': full_url, 'text': link.get_text().strip(), 'external': False})
        
        # Extract images
        images = []
        for img in soup.find_all('img'):
            img_data = {
                'src': img.get('src', ''),
                'alt': img.get('alt', ''),
                'title': img.get('title', ''),
                'has_alt': bool(img.get('alt'))
            }
            images.append(img_data)
        
        # Extract text content
        text_content = soup.get_text()
        word_count = len(text_content.split())
        
        # Extract meta tags
        meta_tags = {}
        for meta in soup.find_all('meta'):
            name = meta.get('name') or meta.get('property') or meta.get('http-equiv')
            content = meta.get('content')
            if name and content:
                meta_tags[name] = content
        
        return {
            'title': title_text,
            'meta_description': meta_description_text,
            'headings': headings,
            'links': links,
            'images': images,
            'text_content': text_content,
            'word_count': word_count,
            'meta_tags': meta_tags,
            'html_length': len(html_content)
        }
    
    def analyze_performance(self, parsed_data: dict, response_time: float, content_size: int):
        """Analyze performance metrics"""
        performance_score = 100
        issues = []
        
        # Response time analysis
        if response_time > 3.0:
            performance_score -= 30
            issues.append("Slow response time (>3 seconds)")
        elif response_time > 1.5:
            performance_score -= 15
            issues.append("Moderate response time (>1.5 seconds)")
        
        # Content size analysis
        if content_size > 1000000:  # 1MB
            performance_score -= 20
            issues.append("Large page size (>1MB)")
        elif content_size > 500000:  # 500KB
            performance_score -= 10
            issues.append("Moderate page size (>500KB)")
        
        # Image optimization
        images_without_alt = len([img for img in parsed_data['images'] if not img['has_alt']])
        if images_without_alt > 0:
            performance_score -= min(images_without_alt * 2, 20)
            issues.append(f"{images_without_alt} images missing alt text")
        
        return {
            'score': max(performance_score, 0),
            'response_time': response_time,
            'content_size': content_size,
            'images_count': len(parsed_data['images']),
            'images_without_alt': images_without_alt,
            'issues': issues
        }
    
    def analyze_seo(self, parsed_data: dict):
        """Analyze SEO factors"""
        seo_score = 100
        issues = []
        
        # Title analysis
        title = parsed_data['title']
        if not title:
            seo_score -= 20
            issues.append("Missing page title")
        elif len(title) > 60:
            seo_score -= 10
            issues.append("Title too long (>60 characters)")
        elif len(title) < 30:
            seo_score -= 5
            issues.append("Title too short (<30 characters)")
        
        # Meta description analysis
        meta_description = parsed_data['meta_description']
        if not meta_description:
            seo_score -= 15
            issues.append("Missing meta description")
        elif len(meta_description) > 160:
            seo_score -= 8
            issues.append("Meta description too long (>160 characters)")
        elif len(meta_description) < 120:
            seo_score -= 5
            issues.append("Meta description too short (<120 characters)")
        
        # Heading structure analysis
        headings = parsed_data['headings']
        if not headings['h1']:
            seo_score -= 15
            issues.append("Missing H1 tag")
        elif len(headings['h1']) > 1:
            seo_score -= 10
            issues.append("Multiple H1 tags found")
        
        # Content analysis
        word_count = parsed_data['word_count']
        if word_count < 300:
            seo_score -= 15
            issues.append("Low word count (<300 words)")
        
        # Internal vs external links
        internal_links = len([link for link in parsed_data['links'] if not link['external']])
        external_links = len([link for link in parsed_data['links'] if link['external']])
        
        if internal_links == 0:
            seo_score -= 10
            issues.append("No internal links found")
        
        return {
            'score': max(seo_score, 0),
            'title_length': len(title),
            'meta_description_length': len(meta_description),
            'word_count': word_count,
            'h1_count': len(headings['h1']),
            'internal_links': internal_links,
            'external_links': external_links,
            'issues': issues
        }
    
    def analyze_technical_health(self, parsed_data: dict, url: str):
        """Analyze technical health factors"""
        technical_score = 100
        issues = []
        
        # HTTPS check
        if not url.startswith('https://'):
            technical_score -= 20
            issues.append("Website not using HTTPS")
        
        # Meta viewport check
        if 'viewport' not in parsed_data['meta_tags']:
            technical_score -= 15
            issues.append("Missing viewport meta tag")
        
        # Structured data check (basic)
        if 'description' not in parsed_data['meta_tags']:
            technical_score -= 10
            issues.append("Missing meta description")
        
        return {
            'score': max(technical_score, 0),
            'https_enabled': url.startswith('https://'),
            'has_viewport': 'viewport' in parsed_data['meta_tags'],
            'issues': issues
        }
    
    def analyze_accessibility(self, parsed_data: dict):
        """Analyze accessibility factors"""
        accessibility_score = 100
        issues = []
        
        # Image alt text analysis
        images_without_alt = len([img for img in parsed_data['images'] if not img['has_alt']])
        total_images = len(parsed_data['images'])
        
        if total_images > 0:
            alt_percentage = ((total_images - images_without_alt) / total_images) * 100
            if alt_percentage < 80:
                accessibility_score -= 25
                issues.append(f"Only {alt_percentage:.0f}% of images have alt text")
            elif alt_percentage < 90:
                accessibility_score -= 15
                issues.append(f"{alt_percentage:.0f}% of images have alt text (should be 100%)")
        
        # Heading structure
        headings = parsed_data['headings']
        if not headings['h1']:
            accessibility_score -= 15
            issues.append("Missing H1 heading for screen readers")
        
        return {
            'score': max(accessibility_score, 0),
            'images_with_alt_percentage': ((total_images - images_without_alt) / total_images * 100) if total_images > 0 else 100,
            'issues': issues
        }
    
    def analyze_schema_and_faq(self, parsed_data: dict, html_content: str):
        """Analyze schema markup and FAQ structure"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Schema analysis
        schema_data = self.detect_schema_markup(soup)
        
        # FAQ analysis  
        faq_data = self.detect_faq_structure(soup, parsed_data)
        
        # Determine checkpoint category
        has_schema = schema_data['has_schema']
        has_faq = faq_data['has_faq']
        
        if has_schema and has_faq:
            checkpoint_category = "both_schema_faq"
            category_label = "✅ Both Schema + FAQ"
            score = 100
        elif has_schema and not has_faq:
            checkpoint_category = "schema_only"
            category_label = "🔵 Schema Only (No FAQ)"
            score = 75
        elif not has_schema and has_faq:
            checkpoint_category = "faq_only"
            category_label = "🟡 FAQ Only (No Schema)"
            score = 50
        else:
            checkpoint_category = "neither"
            category_label = "❌ Neither Schema nor FAQ"
            score = 25
            
        return {
            'score': score,
            'has_schema': has_schema,
            'has_faq': has_faq,
            'checkpoint_category': checkpoint_category,
            'category_label': category_label,
            'schema_details': schema_data,
            'faq_details': faq_data,
            'issues': schema_data['issues'] + faq_data['issues']
        }
    
    def detect_schema_markup(self, soup):
        """Detect various types of schema markup"""
        issues = []
        schema_types = []
        has_schema = False
        
        # JSON-LD Detection
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        json_ld_schemas = []
        
        for script in json_ld_scripts:
            try:
                schema_data = json.loads(script.string)
                if isinstance(schema_data, dict) and '@type' in schema_data:
                    json_ld_schemas.append(schema_data['@type'])
                    schema_types.append(f"JSON-LD: {schema_data['@type']}")
                    has_schema = True
                elif isinstance(schema_data, list):
                    for item in schema_data:
                        if isinstance(item, dict) and '@type' in item:
                            json_ld_schemas.append(item['@type'])
                            schema_types.append(f"JSON-LD: {item['@type']}")
                            has_schema = True
            except (json.JSONDecodeError, KeyError):
                continue
        
        # Microdata Detection
        microdata_elements = soup.find_all(attrs={'itemscope': True})
        microdata_types = []
        
        for element in microdata_elements:
            itemtype = element.get('itemtype')
            if itemtype:
                microdata_types.append(itemtype)
                schema_types.append(f"Microdata: {itemtype}")
                has_schema = True
        
        # RDFa Detection
        rdfa_elements = soup.find_all(attrs={'typeof': True})
        rdfa_types = []
        
        for element in rdfa_elements:
            typeof = element.get('typeof')
            if typeof:
                rdfa_types.append(typeof)
                schema_types.append(f"RDFa: {typeof}")
                has_schema = True
        
        # Check for common schema types
        if not has_schema:
            issues.append("No structured data markup found")
        else:
            # Check for FAQ schema specifically
            faq_schemas = [s for s in json_ld_schemas if 'FAQ' in s or 'Question' in s]
            if not faq_schemas:
                issues.append("No FAQ-specific schema markup found")
        
        return {
            'has_schema': has_schema,
            'json_ld_count': len(json_ld_scripts),
            'microdata_count': len(microdata_elements),
            'rdfa_count': len(rdfa_elements),
            'schema_types': schema_types,
            'json_ld_schemas': json_ld_schemas,
            'microdata_types': microdata_types,
            'rdfa_types': rdfa_types,
            'issues': issues
        }
    
    def detect_faq_structure(self, soup, parsed_data):
        """Detect FAQ structure on the page"""
        issues = []
        has_faq = False
        faq_indicators = []
        
        # Text-based FAQ detection
        text_content = parsed_data.get('text_content', '').lower()
        faq_patterns = [
            r'frequently asked questions?',
            r'f\.?a\.?q\.?s?',
            r'common questions?',
            r'questions? (?:and|&) answers?',
            r'q\s*&\s*a',
            r'help (?:and|&) support'
        ]
        
        for pattern in faq_patterns:
            if re.search(pattern, text_content):
                has_faq = True
                faq_indicators.append(f"Text pattern: {pattern}")
        
        # Heading-based FAQ detection
        all_headings = []
        for level in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            all_headings.extend(parsed_data.get('headings', {}).get(level, []))
        
        faq_heading_patterns = [
            r'faq',
            r'frequently asked',
            r'common questions',
            r'questions?.*answers?',
            r'help.*support'
        ]
        
        for heading in all_headings:
            heading_lower = heading.lower()
            for pattern in faq_heading_patterns:
                if re.search(pattern, heading_lower):
                    has_faq = True
                    faq_indicators.append(f"Heading: {heading}")
                    break
        
        # Structure-based FAQ detection (Q&A pairs)
        question_indicators = soup.find_all(text=re.compile(r'^\s*(?:Q\d*[:.]?|Question\d*[:.]?|\?)', re.IGNORECASE))
        answer_indicators = soup.find_all(text=re.compile(r'^\s*(?:A\d*[:.]?|Answer\d*[:.]?)', re.IGNORECASE))
        
        if len(question_indicators) >= 2 and len(answer_indicators) >= 2:
            has_faq = True
            faq_indicators.append(f"Q&A structure: {len(question_indicators)} questions, {len(answer_indicators)} answers")
        
        # Check for FAQ-specific HTML structures
        faq_containers = soup.find_all(attrs={'class': re.compile(r'faq|question|accordion', re.IGNORECASE)})
        if len(faq_containers) >= 2:
            has_faq = True
            faq_indicators.append(f"FAQ containers: {len(faq_containers)} elements")
        
        # Schema-based FAQ detection
        faq_schema_elements = soup.find_all(attrs={'itemtype': re.compile(r'FAQPage|Question', re.IGNORECASE)})
        if faq_schema_elements:
            has_faq = True
            faq_indicators.append(f"Schema FAQ elements: {len(faq_schema_elements)}")
        
        if not has_faq:
            issues.append("No FAQ structure detected")
        
        return {
            'has_faq': has_faq,
            'faq_indicators': faq_indicators,
            'question_count': len(question_indicators),
            'answer_count': len(answer_indicators),
            'faq_containers': len(faq_containers),
            'issues': issues
        }
    
    def calculate_scores(self, performance_data: dict, seo_data: dict, technical_data: dict, accessibility_data: dict, schema_faq_data: dict):
        """Calculate overall and individual scores"""
        performance_score = performance_data['score']
        seo_score = seo_data['score']
        technical_score = technical_data['score']
        accessibility_score = accessibility_data['score']
        schema_faq_score = schema_faq_data['score']
        
        # Weighted overall score (adjusted for new schema/FAQ component)
        overall_score = int(
            (performance_score * 0.25) +
            (seo_score * 0.35) +
            (technical_score * 0.15) +
            (accessibility_score * 0.10) +
            (schema_faq_score * 0.15)
        )
        
        return {
            'overall': overall_score,
            'performance': performance_score,
            'seo': seo_score,
            'technical': technical_score,
            'accessibility': accessibility_score,
            'schema_faq': schema_faq_score
        }
    
    async def generate_ai_insights(self, parsed_data: dict, performance_data: dict, seo_data: dict, technical_data: dict, url: str):
        """Generate AI-powered insights and recommendations"""
        try:
            # Initialize AI chat
            chat = LlmChat(
                api_key=self.openai_api_key,
                session_id=f"analysis_{int(time.time())}",
                system_message="You are an expert SEO and web performance consultant. Analyze the provided website data and provide specific, actionable recommendations for improvement."
            ).with_model("openai", "gpt-4o-mini").with_max_tokens(1500)
            
            # Prepare analysis data for AI
            analysis_summary = f"""
Website: {url}
Title: {parsed_data.get('title', 'N/A')}
Meta Description: {parsed_data.get('meta_description', 'N/A')}
Word Count: {parsed_data.get('word_count', 0)}
H1 Tags: {len(parsed_data.get('headings', {}).get('h1', []))}
Images: {len(parsed_data.get('images', []))}
Internal Links: {len([l for l in parsed_data.get('links', []) if not l.get('external', True)])}
External Links: {len([l for l in parsed_data.get('links', []) if l.get('external', False)])}

Performance Issues: {', '.join(performance_data.get('issues', []))}
SEO Issues: {', '.join(seo_data.get('issues', []))}
Technical Issues: {', '.join(technical_data.get('issues', []))}

Current Scores:
- Performance: {performance_data.get('score', 0)}/100
- SEO: {seo_data.get('score', 0)}/100
- Technical: {technical_data.get('score', 0)}/100
"""

            user_message = UserMessage(
                text=f"Analyze this website data and provide 5 specific, actionable recommendations to improve SEO and performance. Format as JSON with 'recommendations' array containing objects with 'title', 'description', 'priority' (High/Medium/Low), and 'impact' fields:\n\n{analysis_summary}"
            )
            
            response = await chat.send_message(user_message)
            
            # Try to parse AI response as JSON
            try:
                ai_data = json.loads(response)
                return ai_data
            except json.JSONDecodeError:
                # Fallback if AI doesn't return valid JSON
                return {
                    "recommendations": [
                        {
                            "title": "AI Analysis Available",
                            "description": response[:500] + "..." if len(response) > 500 else response,
                            "priority": "Medium",
                            "impact": "Moderate"
                        }
                    ]
                }
                
        except Exception as e:
            logger.error(f"AI analysis failed: {str(e)}")
            # Return fallback recommendations
            return {
                "recommendations": [
                    {
                        "title": "Optimize Page Speed",
                        "description": "Improve website loading times by optimizing images, enabling compression, and minimizing HTTP requests.",
                        "priority": "High",
                        "impact": "High"
                    },
                    {
                        "title": "Improve SEO Meta Tags",
                        "description": "Ensure all pages have unique, descriptive titles and meta descriptions within recommended character limits.",
                        "priority": "High",
                        "impact": "High"
                    },
                    {
                        "title": "Add Missing Alt Text",
                        "description": "Add descriptive alt text to all images for better accessibility and SEO.",
                        "priority": "Medium",
                        "impact": "Medium"
                    }
                ]
            }

# Initialize analyzer
analyzer = WebsiteAnalyzer()

# API Routes
@api_router.get("/")
async def root():
    return {"message": "AI Website Analyzer API"}

@api_router.post("/analyze", response_model=dict)
async def start_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """Start website analysis"""
    try:
        # Validate URL
        if not request.url:
            raise HTTPException(status_code=400, detail="URL is required")
        
        # Start analysis in background
        background_tasks.add_task(analyzer.analyze_website, request.url, request.session_id)
        
        return {
            "session_id": request.session_id,
            "status": "started",
            "message": "Analysis started"
        }
    except Exception as e:
        logger.error(f"Failed to start analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/progress/{session_id}")
async def get_progress(session_id: str):
    """Get analysis progress"""
    if session_id not in analysis_progress:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return analysis_progress[session_id]

@api_router.get("/result/{session_id}")
async def get_result(session_id: str):
    """Get analysis result"""
    result = await db.analyses.find_one({"session_id": session_id})
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    
    # Remove MongoDB ObjectId for JSON serialization
    if '_id' in result:
        del result['_id']
    
    return result

@api_router.get("/analyses", response_model=List[dict])
async def get_recent_analyses():
    """Get recent analyses"""
    analyses = await db.analyses.find().sort("created_at", -1).limit(10).to_list(10)
    
    # Clean up MongoDB ObjectIds
    for analysis in analyses:
        if '_id' in analysis:
            del analysis['_id']
    
    return analyses

# Legacy routes for compatibility
@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.dict()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.dict())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()