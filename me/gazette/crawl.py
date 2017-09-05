from datetime import datetime, timedelta
from urlparse import urljoin

from twones.operation import operation


@operation()
def crawl_urls(context, data):
    index_url = data.get('urls').get('index_url')
    urls = set()
    date = datetime(2010, 1, 1)

    def qfmt(date):
        return date.strftime('%d.%m.%Y')

    while True:
        # timedelta
        params = {
            'tp': -1,
            'yr': '',
            'fts': '',
            'frm': qfmt(date - timedelta(days=2)),
            'to': qfmt(date + timedelta(days=7))
        }
        doc = context.request_html(index_url, cache=False, params=params)
        for link in doc.findall('.//div[@class="resultinfo"]//a'):
            doc_url = urljoin(index_url, link.get('href'))
            if doc_url not in urls:
                data = {'url': doc_url}
                context.emit(data=data)
            urls.add(doc_url)

        date = date + timedelta(days=7)
        if date > datetime.utcnow():
            break


@operation()
def crawl_record(context, data):
    url = data.get('url')
    source_url = url.replace('OglasniDioDetalji', 'OglasniDioPreuzimanje')
    if context.skip_incremental(source_url):
        return
    res = context.request(source_url)
    if 'aspxerrorpath' in res.url:
        context.log.info("Broken link: %r", source_url)
        return
    meta = {
        'countries': ['me'],
        'extension': 'pdf',
        'mime_type': 'application/pdf',
        'foreign_id': source_url,
        'source_url': source_url
    }
    # aleph_emit_result(meta, res)
