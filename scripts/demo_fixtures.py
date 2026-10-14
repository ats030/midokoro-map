"""Original fictional map entries; no production records or external content."""
import json
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
LABEL = '展示用：架空の地点・固定応答・合成背景／本番データやAIの精度を示すものではありません'
PREFIXES = {'shiseki': '架空の史跡', 'omatsuri': '架空の祭り', 'onsen': '架空の温泉', 'tokusan': '架空の工芸品'}


def rows(kind):
    output = []
    for index, (prefecture, lat, lng) in enumerate([
        ('熊本県', 32.75, 130.70), ('熊本県', 32.92, 131.03), ('大分県', 33.10, 131.25), ('佐賀県', 33.28, 130.05),
    ], 1):
        offset = list(PREFIXES).index(kind) * .035
        row = {'qid': f'local-demo-{kind}-{index}', 'label_ja': f'{PREFIXES[kind]} {index}',
               'label_en': '', 'prefecture': prefecture, 'latitude': lat + offset, 'longitude': lng + offset,
               'description': '画面の操作を確認するために作成した架空の説明です。実在する施設や行事の情報ではありません。',
               'source_url': 'https://example.invalid/demo', 'source_name': 'みどころマップの展示用データ',
               'source_license': '展示用の合成データ', 'address': '展示用の架空住所',
               'categories': [], 'title_ja': '', 'wikipedia_title': ''}
        if kind == 'shiseki':
            row.update(id=f'demo-site-{index}', qid='', designation='unknown', designation_label='展示用', era='架空の時代')
        if kind == 'omatsuri':
            row.update(date='展示用の日程', coordinate_prefecture=prefecture, coordinate_source='demo')
        if kind == 'onsen':
            row.update(spring_types=['単純温泉'], operating_status='unknown')
        if kind == 'tokusan':
            row.update(place='架空の産地', city='架空の町', confidence=0,
                       evidence='展示用に作成', lat=row['latitude'], lng=row['longitude'],
                       production_area='架空の産地', coordinate_kind='municipality_office',
                       coordinate_label='架空の町', coordinate_source_url='https://example.invalid/demo',
                       coordinate_source_name='展示用', region_ids=[], region_scope='unknown',
                       category='kg', maker='', prefecture_level=False)
        output.append(row)
    return output


def geo(name):
    if name == 'geosites':
        feature = {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [130.95, 32.88]},
                   'properties': {'heritage_id': 'demo-geo', 'name': '架空の岩石地点', 'prefecture': '熊本県',
                                  'designation_label': '展示用', 'source_url': 'https://example.invalid/demo'}}
    else:
        feature = {'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': [[[130.60, 32.6], [131.2, 32.6], [131.2, 33.15], [130.6, 33.15], [130.60, 32.6]]]},
                   'properties': {'slug': f'demo-{name}', 'name': '架空の' + ('ジオパーク' if name == 'geoparks' else '公園区域'),
                                  'prefecture': '熊本県', 'prefectures': '熊本県', 'municipalities': ['架空の町'],
                                  'counts': {kind: 2 for kind in PREFIXES}, 'source': 'https://example.invalid/demo',
                                  'source_url': 'https://example.invalid/demo', 'area_label': '展示用', 'designated': '展示用', 'data_year': '展示用'}}
    return {'type': 'FeatureCollection', 'features': [feature], 'meta': {'fixture': True}}


def insert(connection, table, values):
    names = list(values)
    connection.execute(f'INSERT INTO {table} ({",".join(names)}) VALUES ({",".join("?" for _ in names)})', list(values.values()))


def write_test_databases(destination):
    """Build only synthetic SQLite files in an isolated test checkout."""
    destination = Path(destination)
    for kind, table, filename, schema_name in [
        ('shiseki', 'shiseki', 'shiseki.db', 'baseSchema'),
        ('onsen', 'onsen', 'onsen.db', 'baseSchema'),
        ('omatsuri', 'festival', 'festivals.db', 'festivalBaseSchema'),
    ]:
        module = 'festival_service.go' if kind == 'omatsuri' else kind + '_service.go'
        source = (ROOT / f'internal/{kind}/services/{module}').read_text()
        schema = re.search(r'const ' + schema_name + r' = `([\s\S]*?)`', source).group(1)
        path = destination / kind / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise ValueError('Refusing to replace an existing database')
        with sqlite3.connect(path) as database:
            database.executescript(schema)
            for item in rows(kind):
                record = {key: item[key] for key in ['qid', 'label_ja', 'label_en', 'prefecture', 'latitude', 'longitude', 'description']}
                if kind == 'shiseki':
                    record.update(site_id=item['id'], source_url=item['source_url'], source_name=item['source_name'], address=item['address'])
                if kind == 'omatsuri':
                    record.update(date=item['date'], coordinate_prefecture=item['prefecture'])
                insert(database, table, record)
    path = destination / 'tokusan/tokusan.db'
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError('Refusing to replace an existing database')
    fields = ['qid','label_ja','label_en','place','prefecture','city','lat','lng','evidence','confidence',
              'source_url','category','maker','prefecture_level','source_name','description','history','production',
              'production_area','coordinate_kind','coordinate_label','coordinate_source_url','coordinate_source_name',
              'region_ids','region_scope']
    numeric = {'lat', 'lng', 'confidence', 'prefecture_level'}
    with sqlite3.connect(path) as database:
        database.execute('CREATE TABLE tokusan (id INTEGER PRIMARY KEY,' + ','.join(f'{name} {"INTEGER" if name == "prefecture_level" else "REAL" if name in numeric else "TEXT"} NOT NULL' for name in fields) + ')')
        for index, item in enumerate(rows('tokusan')):
            item.update(history='展示用の架空の歴史です。' if index else '', production='展示用の架空の製造方法です。' if index else '', region_ids=json.dumps(item['region_ids']))
            insert(database, 'tokusan', {name: item[name] for name in fields})
