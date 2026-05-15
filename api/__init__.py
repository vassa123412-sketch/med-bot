"""
Medical API integrations: PubMed, ChEMBL, DrugBank
"""
import asyncio
import logging
import xml.etree.ElementTree as ET
from urllib.parse import quote
from typing import List, Optional, Dict
import aiohttp

logger = logging.getLogger(__name__)


class PubMedClient:
    """NCBI PubMed API client"""
    
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def search(self, query: str, max_results: int = 5, sort="relevance") -> List[Dict]:
        """Search PubMed for articles"""
        search_url = f"{self.BASE_URL}/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "sort": sort,
            "retmode": "json",
        }
        
        session = await self._get_session()
        async with session.get(search_url, params=params) as resp:
            data = await resp.json()
        
        ids = data["esearchresult"].get("idlist", [])
        if not ids:
            return []
        
        return await self._fetch_details(ids)
    
    async def _fetch_details(self, ids: List[str]) -> List[Dict]:
        """Fetch article details from PubMed"""
        fetch_url = f"{self.BASE_URL}/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
        }
        
        session = await self._get_session()
        async with session.get(fetch_url, params=params) as resp:
            xml_text = await resp.text()
        
        articles = []
        try:
            root = ET.fromstring(xml_text)
            for article in root.findall("PubmedArticle"):
                medline = article.find("MedlineCitation")
                if medline is None:
                    continue
                
                title_elem = medline.find(".//ArticleTitle")
                title = title_elem.text if title_elem is not None else "Без названия"
                
                journal_elem = medline.find(".//Journal/Title")
                journal = journal_elem.text if journal_elem is not None else ""
                
                year_elem = medline.find(".//Journal/JournalIssue/PubDate/Year")
                year = year_elem.text if year_elem is not None else ""
                
                abstract_elem = article.find(".//Abstract/AbstractText")
                abstract = abstract_elem.text if abstract_elem is not None else ""
                
                authors = []
                for author in medline.findall(".//AuthorList/Author"):
                    last = author.find("LastName")
                    initials = author.find("Initials")
                    if last is not None:
                        name = last.text
                        if initials is not None:
                            name += " " + initials.text
                        authors.append(name)
                
                pmid_elem = medline.find("PMID")
                pmid = pmid_elem.text if pmid_elem is not None else ""
                
                articles.append({
                    "title": title,
                    "journal": journal,
                    "year": year,
                    "authors": ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                    "abstract": abstract[:300] + "..." if len(abstract) > 300 else abstract,
                    "pmid": pmid,
                    "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                })
        except ET.ParseError as e:
            logger.error(f"Failed to parse PubMed XML: {e}")
        
        return articles
    
    async def format_results(self, query: str, max_results: int = 5) -> str:
        """Search and format results for Telegram"""
        articles = await self.search(query, max_results)
        
        if not articles:
            return "📚 По вашему запросу не найдено статей в PubMed."
        
        result = f"📚 **Найдено статей: {len(articles)}**\n\n"
        for i, art in enumerate(articles, 1):
            result += f"**{i}. {art['title']}**\n"
            result += f"📖 {art['journal']}" + (f" ({art['year']})" if art['year'] else "") + "\n"
            result += f"👤 {art['authors']}\n"
            if art['abstract']:
                result += f"📝 {art['abstract']}\n"
            result += f"🔗 {art['link']}\n\n"
        
        result += "_Источник: PubMed (NCBI)_"
        return result
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


class ChEMBLClient:
    """ChEMBL API client for drug information"""
    
    BASE_URL = "https://www.ebi.ac.uk/chembl/api/utils"
    MOLECULE_URL = "https://www.ebi.ac.uk/chembl/api/data/molecule"
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def search_drug(self, drug_name: str) -> List[Dict]:
        """Search for drug in ChEMBL"""
        search_url = f"{self.BASE_URL}/search_by_name.json"
        params = {"name": drug_name, "format": "json"}
        
        session = await self._get_session()
        async with session.get(search_url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("results", [])[:5]
        return []
    
    async def get_molecule_details(self, chembl_id: str) -> Optional[Dict]:
        """Get molecule details"""
        url = f"{self.MOLECULE_URL}/{chembl_id}.json"
        
        session = await self._get_session()
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("molecule", {})
        return None
    
    async def format_drug_info(self, drug_name: str) -> str:
        """Search and format drug info for Telegram"""
        results = await self.search_drug(drug_name)
        
        if not results:
            return f"💊 По запросу '{drug_name}' не найдено информации в ChEMBL."
        
        result = f"💊 **Информация о лекарстве: {drug_name}**\n\n"
        for i, drug in enumerate(results, 1):
            result += f"**{i}. {drug.get('molecule_name', 'Unknown')}**\n"
            result += f"🆔 ChEMBL ID: {drug.get('chembl_id', '')}\n"
            result += f"📋 Тип: {drug.get('molecule_type', '')}\n"
            result += f"🎯 Первый approval: {drug.get('first_approval', 'Не указано')}\n"
            if drug.get('indication'):
                result += f"📌 Показания: {drug['indication'][:200]}...\n"
            result += "\n"
        
        result += "_Источник: ChEMBL (EBI)_"
        return result
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


# Singleton instances
pubmed_client = PubMedClient()
chembl_client = ChEMBLClient()

__all__ = ['pubmed_client', 'chembl_client']
