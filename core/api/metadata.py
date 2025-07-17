import re
import logging
from typing import Optional
from urllib.parse import urlparse
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class MetadataResponse(BaseModel):
    title: str
    description: str
    image: str
    favicon: str
    domain: str

def extract_title_from_url(url: str) -> str:
    """Extracts a readable title from a URL."""
    try:
        parsed_url = urlparse(url)
        path = parsed_url.path
        
        # Get the last segment of the path
        last_segment = path.split('/')[-1] if path != '/' else ''
        
        if not last_segment:
            return parsed_url.hostname or url
        
        # Handle common URL formats
        title = last_segment
        # Replace hyphens and underscores with spaces
        title = re.sub(r'[-_]', ' ', title)
        # Remove file extension
        title = re.sub(r'\.[^/.]+$', '', title)
        # Replace %20 with spaces
        title = title.replace('%20', ' ')
        # Add a space before uppercase letters (to handle CamelCase)
        title = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', title)
        # Capitalize the first letter of each word
        title = ' '.join(word.capitalize() for word in title.split())
        
        return title.strip() if title.strip() else url
    except Exception:
        return url

async def fetch_metadata(url: str) -> MetadataResponse:
    """Fetches OpenGraph and other metadata from a web page."""
    
    # Set request headers to simulate a browser
    headers = {
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'accept-encoding': 'gzip, deflate, br',
        'connection': 'keep-alive',
        'upgrade-insecure-requests': '1',
    }
    
    try:
        # Parse the domain
        parsed_url = urlparse(url)
        domain = parsed_url.hostname
        if domain and domain.startswith('www.'):
            domain = domain[4:]
        
        favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=32"
        fallback_title = extract_title_from_url(url)
        
        timeout = aiohttp.ClientTimeout(total=20)
        
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, allow_redirects=True) as response:
                if response.status != 200:
                    logger.warning("http_error_fetching_metadata", extra={"status_code": response.status, "url": url})
                    return MetadataResponse(
                        title=fallback_title,
                        description="",
                        image="",
                        favicon=favicon_url,
                        domain=domain or ""
                    )
                
                html_content = await response.text()
                
        # Parse HTML using BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract OpenGraph information
        def get_meta_content(property_name: str, name_attr: str = "property") -> str:
            """Gets the content value of a meta tag."""
            meta_tag = soup.find("meta", {name_attr: property_name})
            return meta_tag.get("content", "") if meta_tag else ""
        
        # Prioritize OpenGraph info, then Twitter info
        og_title = get_meta_content("og:title")
        twitter_title = get_meta_content("twitter:title", "name")
        title_tag = soup.find("title")
        html_title = title_tag.get_text().strip() if title_tag else ""
        
        title = og_title or twitter_title or html_title or fallback_title
        
        og_description = get_meta_content("og:description")
        twitter_description = get_meta_content("twitter:description", "name")
        meta_description = get_meta_content("description", "name")
        
        description = og_description or twitter_description or meta_description
        
        og_image = get_meta_content("og:image")
        twitter_image = get_meta_content("twitter:image", "name")
        
        image = og_image or twitter_image
        
        # If the image URL is a relative path, convert it to an absolute path
        if image and not image.startswith(('http://', 'https://')):
            if image.startswith('//'):
                image = f"{parsed_url.scheme}:{image}"
            elif image.startswith('/'):
                image = f"{parsed_url.scheme}://{parsed_url.netloc}{image}"
            else:
                image = f"{parsed_url.scheme}://{parsed_url.netloc}/{image}"
        
        return MetadataResponse(
            title=title,
            description=description,
            image=image,
            favicon=favicon_url,
            domain=domain or ""
        )
        
    except asyncio.TimeoutError:
        logger.warning("metadata_fetch_timeout", extra={"url": url})
        return MetadataResponse(
            title=fallback_title,
            description="",
            image="",
            favicon=favicon_url,
            domain=domain or ""
        )
    except Exception as e:
        logger.error("metadata_fetch_error", extra={"url": url, "error": str(e)})
        return MetadataResponse(
            title=fallback_title,
            description="",
            image="",
            favicon=favicon_url,
            domain=domain or ""
        ) 