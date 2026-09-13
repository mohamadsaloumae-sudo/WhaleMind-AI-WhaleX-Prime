#!/bin/bash
# 🏗️ بناء الواجهة — يرفع نسخة عامل الخدمة تلقائياً.
#    بدونه يبقى المشتركون على النسخة المخزّنة ولا يرون اي تحديث.
set -e
cd /opt/whalex/whalex-dash
SW=public/sw.js
CUR=$(grep -o "whalex-v[0-9]*" "$SW" | head -1)
NUM=$(echo "$CUR" | grep -o '[0-9]*')
NEW="whalex-v$((NUM + 1))"
sed -i "s/$CUR/$NEW/" "$SW"
echo "🔄 عامل الخدمة: $CUR → $NEW"
npm run build
rm -f /opt/whalex/static/assets/*.js /opt/whalex/static/assets/*.css
cp -r dist/* /opt/whalex/static/
systemctl reload nginx
echo "✅ نُشر · $(curl -sk https://whalemindhybridai.online/sw.js | grep -o 'whalex-v[0-9]*')"
