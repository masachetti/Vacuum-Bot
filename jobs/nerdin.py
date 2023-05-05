from typing import List

from bs4 import BeautifulSoup

from enums import Seniority
from jobs.async_url_fetch import fetch_urls
from jobs.utils import sanitize_job_title

## Temporary map
SENIORITY_MAP = {Seniority.Junior: 3, Seniority.Senior: 1, Seniority.Pleno: 2}
PAGES_PER_SCRAPING_PROCESS = 4


def create_search_url(seniority_level: Seniority, page=0):
    base_url = "https://nerdin.com.br/func/FVagaListar.php?"
    home_office = 'UF=HO&'
    seniority = f'CodigoNivel={SENIORITY_MAP[seniority_level]}&'
    pagination = f'CodigoVagaProxima={(page - 1) * 50}&' if page else ''
    return base_url + home_office + seniority + pagination


async def scrap_nerdin_jobs(seniority_level: Seniority) -> List[dict]:
    jobs = []
    page = 0
    loop = True
    while loop:
        urls = [create_search_url(seniority_level, page) for page in
                range(page, page + PAGES_PER_SCRAPING_PROCESS)]
        responses = await fetch_urls(urls)

        for url, content in responses.items():
            soup = BeautifulSoup(content, 'html.parser')
            job_containers = soup.select("div.container")
            job_anchors = [x.select_one('a') for x in job_containers]
            jobs.extend([{'Job': sanitize_job_title(anchor.select_one('span:nth-child(1) b').text),
                          'Apply': 'https://www.nerdin.com.br/' + anchor.get('href')} for anchor in
                         job_anchors])
            if len(job_anchors) < 50:
                loop = False
                break
    return jobs
