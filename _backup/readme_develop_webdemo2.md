# Diplomat 2.0 路 澶栦氦璋堝垽妯℃嫙鍣紙webdemo 2.0锛?
澶氭櫤鑳戒綋澶栦氦璋堝垽 Demo銆備笁涓皥鍒ゅ満锛堝弻杈?/ 澶氳竟 / 涔濇柟瑙傛垬锛夎窇鍦ㄥ悓涓€濂?CountryAgent 寮曟搸涓娿€?
## 鍚姩

鍙屽嚮 **start.bat**锛屾祻瑙堝櫒鎵撳紑 <http://127.0.0.1:8010/>

锛堢鍙?8010锛屽彲涓庢棫鐨?webdemo1.9锛?002锛夊悓鏃惰繍琛岋級

## 椤甸潰缁撴瀯

锛堜互涓嬮〉闈㈠潎浣嶄簬 `site/` 鐩綍锛岀敱鏈湴鏈嶅姟缁熶竴鎻愪緵锛?
```
棣栭〉  site/index.html
 鈹溾攢 瀛︿範妯″紡  site/learn/index.html
 鈹?   鈹溾攢 绗竴鍏?lesson1.html      + notes.html
 鈹?   鈹溾攢 绗簩鍏?learning-level2.html + notes-level2.html
 鈹?   鈹斺攢 绗笁鍏?learning-level3.html + notes-level3.html
 鈹?        鈹斺攢锛堝彸涓婅銆屽瀹屼簡锛屽幓璋堝垽 鈫掋€嶈繘鍏ヨ繃娓￠〉锛? 鈹溾攢 杩囨浮椤? site/select/start.html      鍙岃竟
 鈹?         site/select/start-1vn.html  澶氳竟
 鈹?         site/select/start-watch.html 瑙傛垬
 鈹?   鈹斺攢锛堢‘璁ゅ悗杩涘叆瀵瑰眬锛? 鈹溾攢 瀵瑰眬  site/duel.html / multi.html / observe.html
 鈹?   鈹斺攢锛堢粨鏉熻皥鍒?鈫?澶嶇洏锛? 鈹斺攢 澶嶇洏  site/report/index.html   锛堣鍙?localStorage: neg-report / neg-v2-report锛?```

## 涓?Agent 寮曟搸鐨勬帴鍙?
鍓嶇閫氳繃 `/api/v2/*` 涓庢湰鍦板紩鎿庨€氫俊锛?
| 鎺ュ彛 | 鐢ㄩ€?|
|---|---|
| `POST /api/v2/session` | 寮€灞€锛堟ā寮忋€佽棰樸€佺帺瀹躲€佸鎵嬶級 |
| `GET  /api/v2/state` | 鍙栨渶鏂拌鍥撅紙甯綅銆佹墜鐗屻€侀樀钀ャ€佹儏鎶ヨ处鏈級 |
| `POST /api/v2/say` | 鍑虹墝 + 鍙戣█ |
| `POST /api/v2/deal` | 闈炴寮忔矡閫?|
| `POST /api/v2/intel` | 鎯呮姤澶勭疆锛堟斁椋?鍑哄敭/鎻┛锛?|
| `POST /api/v2/end` | 缁撴潫鏈眬骞惰繑鍥炲鐩樻憳瑕?|
| `GET  /api/v2/meta` | 鍙敤妯″紡涓庤棰?|

## 寮曟搸鏂囦欢

| 鏂囦欢 | 浣滅敤 |
|---|---|
| `server_diplomat.py` | HTTP 鏈嶅姟 + v2 鎺ュ彛 |
| `server.py` | 鏃х増寮曟搸鏍稿績锛堢粨绠椼€佹墜鐗屻€佷簨浠跺崱锛?|
| `view_diplomat.py` | 瑙嗗浘鏋勫缓锛堝墠绔绾︼級 |
| `diplomacy.py` / `bluff.py` / `deckgen.py` | 澶栦氦娓犻亾銆佽櫄寮犲０鍔裤€佺墝搴撶敓鎴?|
| `settlement.py` / `diplomacy_agent.py` | 缁撶畻涓庢櫤鑳戒綋 |
| `demo1.1/` | 鍚勫浗 Agent 涓庢彁绀鸿瘝 |
| `knowledge/` | 璁鐭ヨ瘑搴撲笌浜嬩欢鍗?|

## 闈欐€佸厹搴?
鐩存帴鍙屽嚮 HTML锛坒ile://锛夋椂鏃犳硶杩炴帴寮曟搸锛岄〉闈細鍔犺浇 `assets/sample-views.js` 閲岀殑蹇収鏍蜂緥骞舵彁绀恒€岄潤鎬侀瑙?路 闈炲疄鏃躲€嶃€?
## 璇勫涓庤璁℃潗鏂?
| 鏂囦欢 | 鍐呭 |
|---|---|
| `璇勫浣跨敤璇存槑.md` | 鍚姩鏂瑰紡銆佹帹鑽愯瘎瀹¤矾绾裤€佺晫闈㈤€熸煡銆佸父瑙侀棶棰樸€佹渶灏忛獙鏀舵竻鍗?|
| `鏅鸿兘浣撹璁¤鏄庝功_webdemo2.0.docx` | 鏅鸿兘浣撹璁¤鏄庝功锛?.0 鐗堬紝鍚灦鏋勩€佺畻娉曘€佹帴鍙ｄ笌鍒涙柊鐐癸級 |
