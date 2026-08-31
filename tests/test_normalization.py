from app.normalization import normalize, searchable_text
def test_aliases_and_type():
    r=normalize({'Issue Key':'DEF-1','Short Description':'Login timeout','RCA':'Pool exhausted','Priority':'P1'},'DEFECT','x.xlsx',2)
    assert r['ticket_id']=='DEF-1' and r['summary']=='Login timeout' and r['ticket_type']=='DEFECT'
    assert 'Pool exhausted' in searchable_text(r)
