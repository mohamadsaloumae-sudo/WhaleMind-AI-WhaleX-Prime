import { useLang } from "../context/LangContext.jsx";

/**
 * 📄 سياسة الخصوصية — صفحة مستقلّة برابط ثابت /privacy.
 * جوجل بلاي تطلب رابطاً مباشراً يعمل بلا تسجيل دخول، ولا تقبل
 * مرساة داخل صفحة أخرى (#privacy).
 */
export default function Privacy() {
  const { lang } = useLang();
  const ar = lang !== "en";
  const S = ({ t, children }) => (
    <section style={{ marginBottom: 22 }}>
      <h3 style={{ fontSize: 15, color: "var(--brand,#0fa392)",
                   margin: "0 0 8px" }}>{t}</h3>
      <div style={{ fontSize: 13.5, color: "var(--txt-2,#a8bfc9)",
                    lineHeight: 2 }}>{children}</div>
    </section>
  );
  return (
    <div style={{ maxWidth: 760, margin: "0 auto", padding: "8px 4px 48px",
                  direction: ar ? "rtl" : "ltr",
                  textAlign: ar ? "right" : "left" }}>
      {/* ↩️ زرّ رجوع — الصفحة تُفتَح مستقلّة بلا شريط تنقّل،
          فبلا هذا الزرّ يعلق الزائر فيها. */}
      <button id="wxBack" onClick={() => {
        if (window.history.length > 1) window.history.back();
        else window.location.href = "/";
      }} style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        background: "none", border: "1px solid var(--line,#24404e)",
        color: "var(--txt-2,#a8bfc9)", borderRadius: 10,
        padding: "7px 14px", fontSize: 13, cursor: "pointer",
        fontFamily: "inherit", marginBottom: 14,
      }}>{ar ? "→ رجوع" : "← Back"}</button>

      <h2 style={{ fontSize: 20, margin: "6px 0 4px" }}>
        {ar ? "🔒 سياسة الخصوصية" : "🔒 Privacy Policy"}
      </h2>
      <div style={{ fontSize: 12, color: "var(--txt-3,#7c98a4)",
                    marginBottom: 20 }}>
        {ar ? "آخر تحديث: أغسطس 2026" : "Last updated: August 2026"}
      </div>

      <S t={ar ? "من نحن" : "Who we are"}>
        {ar ? "وِيل إكس منصّة تحليل وإشارات تداول للعملات الرقمية. لا نحتفظ بأموالك ولا ننقلها ولا نُبادلها. أموالك تبقى في حسابك على المنصّة التي تختارها."
            : "WhaleX is a crypto analysis and trading-signal platform. We never hold, transfer, or exchange your funds. Your money stays in your own exchange account."}
      </S>

      <S t={ar ? "ما الذي نجمعه" : "What we collect"}>
        {ar ? <>
          • البريد الإلكتروني واسم المستخدم عند التسجيل<br/>
          • مفاتيح واجهة برمجة المنصّة (API) التي تُدخلها بنفسك<br/>
          • عنوان الإنترنت (IP) والدولة ونوع الجهاز لأغراض الأمان<br/>
          • سجلّ صفقاتك المنفَّذة لعرضه لك ولحساب أدائك
        </> : <>
          • Email and username at signup<br/>
          • Exchange API keys that you enter yourself<br/>
          • IP address, country and device type for security<br/>
          • Your executed trades, to show you your own performance
        </>}
      </S>

      <S t={ar ? "مفاتيح المنصّة" : "Exchange API keys"}>
        {ar ? "تُحفَظ مشفّرة على خادمنا وتُستعمل حصراً لتنفيذ الصفقات التي تختار تفعيلها. ولا نطلب صلاحية السحب أبداً، ولا نستطيع سحب أموالك حتى لو أردنا. ويمكنك إلغاء المفتاح من منصّتك في أي لحظة."
            : "Stored encrypted on our server and used solely to execute the trades you enable. We never request withdrawal permission and cannot move your funds. You may revoke the key from your exchange at any time."}
      </S>

      <S t={ar ? "مع من نشارك بياناتك" : "Who we share with"}>
        {ar ? "لا نبيع بياناتك ولا نشاركها مع أي طرف ثالث لأغراض تسويقية. والاتّصال الوحيد الخارجيّ هو بمنصّة التداول التي ربطتَها أنت، لتنفيذ أوامرك."
            : "We do not sell or share your data with third parties for marketing. The only external connection is to the exchange you linked, to execute your orders."}
      </S>

      <S t={ar ? "حقوقك" : "Your rights"}>
        {ar ? "يمكنك طلب حذف حسابك وكل بياناتك في أي وقت عبر صفحة الدعم داخل التطبيق، ونُنفّذه خلال سبعة أيام. ويمكنك إيقاف التداول الآليّ أو حذف مفتاحك فوراً من إعداداتك."
            : "You may request deletion of your account and all data at any time via in-app Support; we comply within seven days. You can disable auto-trading or remove your key instantly from settings."}
      </S>

      <S t={ar ? "تنبيه المخاطرة" : "Risk disclosure"}>
        {ar ? "هذا التطبيق للأغراض التحليلية والمعلوماتية. ولا يُقدّم نصيحة استثمارية شخصية. والتداول ينطوي على مخاطرة كبيرة قد تشمل خسارة رأس المال، والأداء السابق لا يضمن نتائج مستقبلية. وقرار التداول قرارك وحدك."
            : "This app is for analytical and informational purposes and does not provide personalized investment advice. Trading carries substantial risk including loss of capital; past performance does not guarantee future results. All trading decisions are yours alone."}
      </S>

      <S t={ar ? "التواصل" : "Contact"}>
        <span dir="ltr">support@whalemindhybridai.online</span>
      </S>

      <button onClick={() => {
        if (window.history.length > 1) window.history.back();
        else window.location.href = "/";
      }} style={{
        width: "100%", marginTop: 24, padding: "12px 0",
        background: "var(--brand,#0fa392)", border: "none",
        borderRadius: 12, color: "#03151a", fontSize: 14.5,
        fontWeight: 700, cursor: "pointer", fontFamily: "inherit",
      }}>{ar ? "رجوع إلى التطبيق" : "Back to app"}</button>
    </div>
  );
}
