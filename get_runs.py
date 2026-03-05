import urllib.request, json
req = urllib.request.Request('https://api.github.com/repos/Airamc76/Trading-Bot/actions/runs', headers={'User-Agent': 'Mozilla/5.0'})
res = urllib.request.urlopen(req)
data = json.loads(res.read())
for r in data.get('workflow_runs', [])[:10]:
    msg = r.get('head_commit',{}).get('message', '').splitlines()[0] if r.get('head_commit') else ''
    print(f"{r['name']} | {r['status']} | {r['conclusion']} | {r['created_at']} | {msg}")
