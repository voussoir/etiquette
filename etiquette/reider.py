for p in P.get_photos():
    g=P.cur.execute('UPDATE photos SET id==? WHERE id==?', [p.id[-12:], p.id])
    g=P.cur.execute('UPDATE photo_tag_rel SET photoid==? WHERE photoid==?', [p.id[-12:], p.id])
    g=P.cur.execute('UPDATE album_photo_rel SET photoid==? WHERE photoid==?', [p.id[-12:], p.id])

for t in P.get_tags():
    g=P.cur.execute('UPDATE tags SET id==? WHERE id==?', [t.id[-12:], t.id])
    g=P.cur.execute('UPDATE photo_tag_rel SET tagid==? WHERE tagid==?', [t.id[-12:], t.id])
    g=P.cur.execute('UPDATE tag_group_rel SET parentid==? WHERE parentid==?', [t.id[-12:], t.id])
    g=P.cur.execute('UPDATE tag_group_rel SET memberid==? WHERE memberid==?', [t.id[-12:], t.id])

for a in P.get_albums():
    g=P.cur.execute('UPDATE albums SET id==? WHERE id==?', [a.id[-12:], a.id])
    g=P.cur.execute('UPDATE tag_group_rel SET parentid==? WHERE parentid==?', [a.id[-12:], a.id])
    g=P.cur.execute('UPDATE tag_group_rel SET memberid==? WHERE memberid==?', [a.id[-12:], a.id])
    g=P.cur.execute('UPDATE album_photo_rel SET albumid==? WHERE albumid==?', [a.id[-12:], a.id])