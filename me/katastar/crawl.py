import hashlib
from itertools import count
from twones.operation import operation
from twones.tools.db import db_connect


def init_session(context, region, login_url, elogin_url):
    context.new_session()
    doc = context.request_html(elogin_url, cache=False)
    login = {}
    for inp in doc.findall('.//input'):
        login[inp.get('name')] = inp.get('value')
    for opt in doc.findall('.//option'):
        if region == opt.get('value'):
            login['opstinaSchema'] = opt.get('value')
            login['nazivIzabraneOpstine'] = opt.text
    login['username'] = 'KORISNIK'
    login['password'] = 'KORISNIK'
    context.request(login_url, cache=False, method='POST', data=login)
    csrftoken = login.get('CSRFToken')
    return csrftoken


@operation()
def get_regions(context, data):
    elogin_url = data.get('urls').get('elogin_url')
    doc = context.request_html(elogin_url, cache=False)
    for opt in doc.findall('.//option'):
        opt_data = data.copy()
        region = {'region': opt.get('value')}
        opt_data.update(region)
        context.emit(data=opt_data)


@operation()
def scrape_parcel(context, data):
    parcel = data.get('parcel')
    csrftoken = data.get('csrftoken')
    args = data.get('args')
    nepo_ajax = data.get('urls').get('nepo_ajax')
    post_data = {
        'searchCriteria': '4',
        'list': parcel.get('broj_lista'),
        'brojParcele': parcel.get('brojParcele'),
        'CSRFToken': csrftoken
    }
    post_data.update(args)
    id_data = post_data.copy()
    del id_data['CSRFToken']
    foreign_id = hashlib.md5()
    foreign_id.update(nepo_ajax)
    foreign_id.update(str(id_data))
    foreign_id = foreign_id.hexdigest()
    if context.skip_incremental(nepo_ajax, foreign_id):
        return
    res = context.request(nepo_ajax, method='POST', data=post_data,
                          foreign_id=foreign_id)
    parcel['broj_parcele'] = parcel.pop('brojParcele')
    parcel['opstina_id'] = args.get('opstinaId')
    parcel['opstina_name'] = args.get('nazivOpstine')
    parcel['kat_optina_id'] = args.get('katastarskaOpstinaId')
    parcel['kat_optina_name'] = args.get('nazivKatastarskeOpstine')
    parcel['data'] = res.content
    db = db_connect()
    db['me_katastar'].insert(parcel)

    context.log.info("Got: %s, %s, parcel %s (%s), length: %s",
                     args.get('nazivOpstine'),
                     args.get('nazivKatastarskeOpstine'),
                     parcel['broj_parcele'],
                     parcel['podbroj'],
                     len(res.content))


@operation()
def scrape_brojs(context, data):
    args = data.get('args')
    csrftoken = data.get('csrftoken')
    nepo_ajax = data.get('urls').get('nepo_ajax')
    fails = 0
    for broj in count(1):
        if fails > 100:
            context.log.info("No more parcels: %s, %s: max %s",
                             args.get('nazivOpstine'),
                             args.get('nazivKatastarskeOpstine'),
                             broj)
            return

        post_data = {
            'searchCriteria': '2',
            'list': '',
            'brojParcele': broj,
            'CSRFToken': csrftoken
        }
        post_data.update(args)
        id_data = post_data.copy()
        del id_data['CSRFToken']
        foreign_id = hashlib.md5()
        foreign_id.update(nepo_ajax)
        foreign_id.update(str(id_data))
        foreign_id = foreign_id.hexdigest()
        if context.skip_incremental(nepo_ajax, foreign_id):
            continue
        res = context.request_json(nepo_ajax, method='POST', data=post_data,
                                   foreign_id=foreign_id)
        parcels = res.get('searchResult').get('listaParcela').get('rows')
        fails += 1
        for parcel in parcels:
            data['args'] = args
            data['parcel'] = parcel
            context.emit(data=data)
            fails = 0


@operation()
def scrape_items(context, data):
    region = data.get('region')
    urls = data.get('urls')
    elogin_url = urls.get('elogin_url')
    login_url = urls.get('login_url')
    csrftoken = init_session(context, region, login_url, elogin_url)
    doc = context.request_html(urls.get('nepo_url'), cache=False)
    for item in doc.findall('.//div[@class="accordionSubItem"]/a'):
        _, args = item.get('onclick').split('(', 1)
        args = args.strip(')').split(', ')
        args = {
            'opstinaId': args[0],
            'nazivOpstine': args[1].strip("'"),
            'katastarskaOpstinaId': args[2],
            'nazivKatastarskeOpstine': args[3].strip("'")
        }
        data['args'] = args
        data['csrftoken'] = csrftoken
        context.emit(data=data)
        csrftoken = init_session(context, region, login_url, elogin_url)
