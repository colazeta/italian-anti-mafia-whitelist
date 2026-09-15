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
def test_history_filters_snapshots_exports_and_navigation(width,tmp_path):
    with playwright.sync_playwright() as p:
        binary=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH') or shutil.which('chromium')
        browser=p.chromium.launch(executable_path=binary,headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':width,'height':950},locale='it-IT')
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        load_page(page)
        page.locator('[data-view="history"]').click()
        assert page.locator('#h-authority').input_value()=='fixture'
        assert '30 giorni' in page.locator('#h-comparison').inner_text()
        assert page.locator('.history-metrics strong').all_text_contents()==['30 giorni','+1','1','0','1','1']
        page.locator('#h-status').select_option('listed')
        assert page.locator('.history-metrics strong').nth(1).inner_text()=='+1'
        page.locator('[data-view="updates"]').click()
        assert page.locator('#u-status').input_value()=='listed'
        assert 'unico intervallo' in page.locator('#view-updates').inner_text()
        page.locator('#u-type').select_option('data_changed')
        with page.expect_download() as pending:page.locator('#view-updates [data-h-export="csv"]').click()
        exported=pending.value.path().read_text(encoding='utf-8-sig')
        assert 'data_changed' in exported and 'baseline' not in exported
        page.locator('#view-updates button[data-h-edition]').click()
        assert page.locator('#view-history').is_visible()
        page.locator('#h-mode').select_option('asof')
        page.locator('#h-asof').fill('2026-06-15');page.locator('#h-asof').dispatch_event('change')
        assert '1 presenze' in page.locator('#view-history').inner_text()
        with page.expect_download() as pending:page.locator('#view-history [data-h-export="json"]').click()
        exported=json.loads(pending.value.path().read_text())
        assert len(exported['editions'])==1 and exported['editions'][0]['reference_date']=='2026-06-01'
        page.locator('#h-asof').fill('2026-01-01');page.locator('#h-asof').dispatch_event('change')
        assert '1 elenchi senza una base anteriore' in page.locator('#view-history').inner_text()
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
