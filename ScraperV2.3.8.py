#!/usr/bin/env python3

import os, re, time, random, requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

class StoryScraperFramework:
    def __init__(self, base_url, downloads_folder="downloads"):
        self.base_url = base_url
        self.downloads_folder = downloads_folder
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        os.makedirs(self.downloads_folder, exist_ok=True)

    def make_request_with_retry(self, url, max_retries=3):
        blocked = ['reddit','twitter','facebook','twitch']
        host = urlparse(url).hostname.lower() if urlparse(url).hostname else ''
        if any(k in host for k in blocked): return None
        for attempt in range(max_retries+1):
            try:
                delay = random.uniform(1.0, 3.0) if attempt==0 else random.uniform(2**attempt, 2**(attempt+1))
                time.sleep(delay)
                r = self.session.get(url, timeout=30)
                r.raise_for_status()
                return r
            except requests.RequestException as e:
                if attempt==max_retries:
                    print(f"[ERROR] {url} failed after {max_retries+1} tries: {e}")
                    return None
                else:
                    print(f"[WARNING] {url} attempt {attempt+1}: {e}")

    def sanitize_filename(self, fn):
        fn = re.sub(r'[<>:"/\\|?*]', '', fn)
        fn = re.sub(r'\s+',' ',fn).strip()[:200]
        return fn if fn else "untitled"

    def extract_story_links(self, soup):
        sels = [
            'a[href*="/s/"]','h3 a[href*="/s/"]','h4 a[href*="/s/"]',
            '.story-title a','div.story-list h3 a','div.content-item a[href*="story"]',
            'article h2 a','h3 a, h4 a, h2 a'
        ]
        found=[]
        for s in sels:
            links=soup.select(s)
            if links:
                for l in links:
                    href=l.get('href')
                    if href:
                        full=urljoin(self.base_url,href)
                        t=l.get_text(strip=True) or "Untitled"
                        found.append((t,full))
                break
        seen=set(); uniq=[]
        for t,u in found:
            if u not in seen:
                seen.add(u); uniq.append((t,u))
        return uniq

    def extract_story_content(self, soup, story_url):
        title=""
        t_sels=['h1','h1.headline','h1.story-title','h1.title','.story-title','.title',
                'h2.entry-title','header h1','div.story-header h1','[class*="title"] h1',
                'h1.storyname','div.story-header h2']
        for s in t_sels:
            el=soup.select_one(s)
            if el: title=el.get_text(strip=True); break
        if not title: print("[WARNING] no title")
        body_sels=['div.story-text p','.story-content p','.story-body p','#story p',
                   'div[class*="story"] p','.content p','.entry-content p','div.content p',
                   'article p','#story-text p','.post-content p','div.text p','main p','p']
        paras=[]
        for s in body_sels:
            ps=soup.select(s)
            if ps:
                val=[]
                for p in ps:
                    text=p.get_text(strip=True)
                    if text and len(text)>10 and not any(a.get('href','').lower().startswith('/s/') for a in p.find_all('a')):
                        val.append(text)
                if val and len(val)>1: paras=val; break
        if not paras:
            ps=soup.find_all('p')
            if ps: paras=[p.get_text(strip=True) for p in ps if p.get_text(strip=True) and len(p.get_text(strip=True))>20]
        ch_links=[]
        n_sels=['a[href*="chapter"]','a[href*="page"]','.next-chapter a','.pagination a[href*="page"]']
        for s in n_sels:
            links=soup.select(s)
            for l in links:
                href=l.get('href')
                if href and ('next' in l.get_text().lower() or 'chapter' in href.lower() or l.get_text().strip().isdigit()):
                    ch_links.append(urljoin(story_url,href))
        series=None
        se=soup.select_one('a.z_t[href*="/series/se/"]')
        if se: series=urljoin(self.base_url,se['href'])
        return title,paras,ch_links,series

    def find_series_link_from_all_pages(self, story_url):
        done=set(); todo=[story_url]
        while todo:
            u=todo.pop(0)
            if u in done: continue
            done.add(u)
            r=self.make_request_with_retry(u)
            if not r: continue
            soup=BeautifulSoup(r.content,'html.parser')
            _,_,nexts,ser=self.extract_story_content(soup,u)
            if ser: return ser
            for n in nexts:
                if n not in done and n not in todo: todo.append(n)
        return None

    def create_pdf(self, title, paras, filename):
        try:
            fp=os.path.join(self.downloads_folder,f"{filename}.pdf")
            doc=SimpleDocTemplate(fp,pagesize=letter)
            styles=getSampleStyleSheet(); story=[]
            story.append(Paragraph(title,styles['Title'])); story.append(Spacer(1,12))
            for item in paras:
                if isinstance(item,str) and item.startswith("Chapter "):
                    story.append(Paragraph(item,styles['Heading1'])); story.append(Spacer(1,24))
                elif item.startswith("PART "):
                    story.append(Paragraph(item,styles['Heading2'])); story.append(Spacer(1,12))
                else:
                    if item.strip():
                        safe=item.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
                        story.append(Paragraph(safe,styles['Normal'])); story.append(Spacer(1,6))
            doc.build(story); return True
        except Exception as e:
            print(f"[ERROR] PDF fail {title}: {e}"); return False

    def scrape_story(self, stitle, surl, full_series=False):
        print(f"Story: {stitle}")
        series=None
        if full_series: series=self.find_series_link_from_all_pages(surl)
        if full_series and series:
            print(f"series found, scraping series for {stitle}")
            sr=self.make_request_with_retry(series)
            if sr:
                soup_series=BeautifulSoup(sr.content,'html.parser')
                st_el=soup_series.select_one('h1')
                st=st_el.get_text(strip=True) if st_el else stitle
                safe=self.sanitize_filename(st)
                path=os.path.join(self.downloads_folder,f"{safe}.pdf")
                if os.path.exists(path):
                    print(f"[SKIP] {safe}.pdf exists"); return True
                ch_sels=['ul.series__works a.br_rj[href*="/s/"]','div.sl-list a.br_rj[href*="/s/"]',
                         'div.sl-list a[href*="/s/"]','div.series-nav a[href*="/s/"]']
                ch_links=[]
                for s in ch_sels:
                    es=soup_series.select(s)
                    if es:
                        for e in es:
                            href=e.get('href')
                            if href and '/s/' in href:
                                full=href if href.startswith('http') else urljoin(self.base_url,href)
                                ch_t=e.get_text(strip=True)
                                m=re.search(r'(?:Ch\.?|Pt\.?)\s*(\d+)(?:-\d+)?',ch_t,re.I)
                                if m: num=int(m.group(1))
                                elif ch_t.strip()==st.strip() or ch_t.lower().startswith(st.lower()): num=1
                                else: num=999
                                ch_links.append((ch_t,full,num))
                        if ch_links: break
                if ch_links:
                    ch_links.sort(key=lambda x:x[2])
                    allc=[]; cnum=1
                    for ct,curl,_ in ch_links:
                        print(f"  {ct}")
                        pages=[curl]; done=set(); part=1; pc=[]
                        while pages:
                            cu=pages.pop(0)
                            if cu in done: continue
                            done.add(cu)
                            pr=self.make_request_with_retry(cu)
                            if not pr: continue
                            ps=BeautifulSoup(pr.content,'html.parser')
                            _,pp,nexts,_=self.extract_story_content(ps,cu)
                            if pp:
                                if part>1: pc.append(f"PART {part}")
                                pc.extend(pp); print(f"    Part {part} ok")
                            for n in nexts:
                                if n not in done and n not in pages: pages.append(n)
                            part+=1
                        allc.append(f"Chapter {cnum}: {ct}" if cnum==1 else f"\nChapter {cnum}: {ct}")
                        allc.extend(pc); cnum+=1
                    if allc and self.create_pdf(st,allc,safe):
                        print(f"Done: {st} saved"); return True
        print(f"  single story mode for {stitle}")
        r=self.make_request_with_retry(surl)
        if not r: return False
        soup=BeautifulSoup(r.content,'html.parser')
        t,pp,ch_links,_=self.extract_story_content(soup,surl)
        ft=t or stitle; safe=self.sanitize_filename(ft)
        path=os.path.join(self.downloads_folder,f"{safe}.pdf")
        if os.path.exists(path):
            print(f"[SKIP] {safe}.pdf exists"); return True
        allc=[]; done=set(); todo=[surl]; part=1
        while todo:
            cu=todo.pop(0)
            if cu in done: continue
            done.add(cu)
            if cu==surl: paras=pp; chs=ch_links
            else:
                rr=self.make_request_with_retry(cu)
                if not rr: continue
                ps=BeautifulSoup(rr.content,'html.parser')
                _,paras,chs,_=self.extract_story_content(ps,cu)
            if paras:
                if part>1: allc.append(f"PART {part}")
                allc.extend(paras); print(f"    Part {part} ok")
            for ch in chs:
                if ch not in done and ch not in todo: todo.append(ch)
            part+=1
        if allc and self.create_pdf(ft,allc,safe):
            print(f"Done: {ft} saved"); return True
        else:
            print(f"[ERROR] no content {stitle}"); return False

    def get_next_page_url(self, soup, cur):
        sels=['a[href*="page="]','.pagination .next','a[rel="next"]','.page-numbers.next']
        if soup:
            for s in sels:
                ls=soup.select(s)
                for l in ls:
                    href=l.get('href')
                    if href and ('next' in l.get_text().lower() or f'page={cur+1}' in href):
                        return urljoin(self.base_url,href)
        if '?' in self.base_url:
            if 'page=' in self.base_url:
                nxt=re.sub(r'page=\d+',f'page={cur+1}',self.base_url)
            else: nxt=f"{self.base_url}&page={cur+1}"
        else: nxt=f"{self.base_url}?page={cur+1}"
        if self.base_url.startswith('https://tags.literotica.com/'):
            nxt=f"{self.base_url.split('?')[0]}?page={cur+1}"
        return nxt

    def scrape_category(self, max_pages=10):
        print(f"Category: {self.base_url}")
        cur=1; found=0; saved=0; done=set()
        while cur<=max_pages:
            page=self.base_url if cur==1 else self.get_next_page_url(None,cur)
            if not page or page in done: break
            done.add(page)
            r=self.make_request_with_retry(page)
            if not r: break
            soup=BeautifulSoup(r.content,'html.parser')
            stories=self.extract_story_links(soup)
            if not stories: break
            print(f"{len(stories)} stories on page {cur}")
            found+=len(stories)
            for i,(st,surl) in enumerate(stories,1):
                print(f"Story {i}/{len(stories)}")
                if self.scrape_story(st,surl,full_series=True): saved+=1
            cur+=1
        print(f"Done! found:{found} saved:{saved}")

    def scrape_single_story(self):
        print(f"Single: {self.base_url}")
        return self.scrape_story("Unknown",self.base_url,full_series=True)

def main():
    # place url here
    TARGET_URL="https://www.example.com"
    MAX_PAGES=5
    FOLDER="downloads"
    try:
        s=StoryScraperFramework(TARGET_URL,FOLDER)
        if '/s/' in TARGET_URL: s.scrape_single_story()
        else: s.scrape_category(max_pages=MAX_PAGES)
    except KeyboardInterrupt:
        print("\n[STOP] by user")
    except Exception as e:
        print(f"[ERROR] {e}"); import traceback; traceback.print_exc()

if __name__=="__main__":
    main()
