"""Rendered interactions with internally consistent synthetic fixtures, offline."""
import json
import os
from pathlib import Path
import re
import shutil

import pytest
playwright = pytest.importorskip('playwright.sync_api')
from test_public_history import fixture_registry
from white_list_archive.publishing.public_history import compare_releases

ROOT=Path(__file__).resolve().parents[1]


def load_page(page, missing_history=False):
    root=ROOT/'public-site'
    before=fixture_registry()
    current=fixture_registry('2026-07-01','b'*64,('listed','listed','pending'))
    history=compare_releases(before,current)
    site=json.loads((root/'data/site.json').read_text())
    data={'./data/registry.json':current,'./data/history.json':None if missing_history else history,'./data/site.json':site,'./data/prefectures.json':{'meta':{'national_index_url':'https://example.test/index'},'prefectures':[{'authority_key':'fixture','jurisdiction_name':'Fixture Prefecture','mapping_status':'published','published_registers':['Fixture register'],'official_white_list_urls':['https://example.test/page']}]}}
    html=re.sub(r'<script src="[^"]+"></script>','',(root/'index.html').read_text())
    html=re.sub(r'<link rel="stylesheet"[^>]+>','',html)
    page.set_content(html,wait_until='domcontentloaded')
    page.add_style_tag(content=(root/'styles.css').read_text())
    page.evaluate('(data)=>{window.fetch=async path=>({ok:!!data[path],status:data[path]?200:404,json:async()=>data[path]});}',data)
    for name in ('summary.js','history.js','app.js'):page.add_script_tag(content=(root/name).read_text())
    page.wait_for_selector('#reg-authority')


@pytest.mark.parametrize('width',[1440,390])
def test_history_is_simple_prefecture_delta_view(width,tmp_path):
    with playwright.sync_playwright() as p:
        binary=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH') or shutil.which('chromium')
        browser=p.chromium.launch(executable_path=binary,headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':width,'height':950},locale='it-IT')
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        load_page(page)
        page.locator('[data-view="history"]').click()
        assert page.locator('#h-authority').input_value()=='fixture'
        text=page.locator('#view-history').inner_text()
        assert 'Storico per Prefettura' in text
        assert '30 giorni' in text
        assert 'Nuove presenze osservate nell’elenco' in text
        assert page.locator('.history-series-table tbody tr').count()==1
        assert page.locator('.history-delta').count()==2
        first_delta=page.locator('.history-delta').first.locator('tbody tr').first.all_text_contents()
        assert any('+1' in item for item in first_delta)
        observed=page.locator('.history-delta').nth(1).inner_text()
        assert '1' in observed and '0' in observed
        assert page.locator('.history-metrics').count()==0
        assert page.locator('.history-timeline').count()==0
        assert page.get_by_role('button',name='Aggiornamenti',exact=True).count()==0
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
        assert not errors
        page.screenshot(path=str(tmp_path/f'history-{width}.png'),full_page=True)
        browser.close()


def test_unavailable_history_does_not_disable_current_registry():
    with playwright.sync_playwright() as p:
        binary=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH') or shutil.which('chromium')
        browser=p.chromium.launch(executable_path=binary,headless=True,args=['--no-sandbox'])
        page=browser.new_page();load_page(page,missing_history=True)
        assert page.locator('#reg-authority').is_visible()
        page.locator('[data-view="history"]').click()
        assert 'non disponibile' in page.locator('#view-history').inner_text().lower()
        page.locator('[data-view="registry"]').click()
        assert page.locator('#reg-authority').is_visible()
        browser.close()
