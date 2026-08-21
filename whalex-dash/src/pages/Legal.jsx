import { useState } from "react";
import { useLang } from "../context/LangContext.jsx";

/**
 * 📄 الشروط · الخصوصية · الاسترداد — في صفحة واحدة بتبويبات.
 *    ثلاث صفحات منفصلة تشتّت، والمستخدم يقرأها معاً عادةً.
 */
export default function Legal() {
  const { lang } = useLang();
  const ar = lang !== "en";
  const [tab, setTab] = useState(
    () => (window.location.hash || "").replace("#", "") || "terms"
  );

  const TABS = ar
    ? [["terms", "الشروط والأحكام"], ["privacy", "الخصوصية"], ["refund", "الاسترداد"]]
    : [["terms", "Terms"], ["privacy", "Privacy"], ["refund", "Refunds"]];

  const S = ({ children }) => (
    <h3 style={{ fontSize: 17, fontWeight: 800, color: "var(--txt-1)", margin: "26px 0 10px" }}>
      {children}
    </h3>
  );
  const P = ({ children }) => (
    <p style={{ fontSize: 14.5, lineHeight: 2.05, color: "var(--txt-2)", margin: "0 0 12px" }}>
      {children}
    </p>
  );
  const L = ({ children }) => (
    <li style={{ fontSize: 14.5, lineHeight: 2.05, color: "var(--txt-2)", marginBottom: 9 }}>
      {children}
    </li>
  );

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", paddingBottom: 40 }}>
      <div style={{ display: "flex", gap: 7, marginBottom: 20, flexWrap: "wrap" }}>
        {TABS.map(([k, label]) => (
          <button key={k} onClick={() => { setTab(k); window.location.hash = k; }}
            style={{
              padding: "8px 15px", borderRadius: 10, cursor: "pointer",
              fontSize: 12.5, fontWeight: tab === k ? 800 : 600,
              background: tab === k ? "rgba(45,212,191,.14)" : "transparent",
              border: `1px solid ${tab === k ? "rgba(45,212,191,.45)" : "rgba(255,255,255,.1)"}`,
              color: tab === k ? "var(--brand)" : "var(--txt-3)",
              transition: "all .18s",
            }}>{label}</button>
        ))}
      </div>

      <div className="card" style={{ padding: "18px 20px 24px" }}>
        {tab === "terms" && (
          <>
            <S>{ar ? "طبيعة الخدمة" : "What this service is"}</S>
            <P>{ar
              ? "واليكس برايم أداة برمجية ترصد فرص التداول وتنفّذها آلياً على حسابك في منصّة تداول تملكها أنت. نحن لسنا وسيطاً مالياً ولا مستشاراً استثمارياً ولا ندير أموالاً نيابةً عنك."
              : "WhaleX Prime is software that detects trading setups and executes them automatically on an exchange account you own. We are not a broker, not an investment adviser, and we do not manage funds on your behalf."}</P>

            <S>{ar ? "أموالك" : "Your funds"}</S>
            <P>{ar
              ? "رأس مالك يبقى في حسابك على منصّتك طوال الوقت. المفتاح الذي تمنحنا إياه للتداول فقط ولا يملك صلاحية السحب. ولا نستلم منك أموالاً إطلاقاً عدا قيمة الاشتراك."
              : "Your capital stays in your own exchange account at all times. The key you grant us is trade-only and cannot withdraw. We never receive funds from you other than the subscription fee."}</P>

            <S>{ar ? "مسؤوليتك" : "Your responsibility"}</S>
            <ul style={{ paddingInlineStart: 20, margin: 0 }}>
              <L>{ar ? "أنت تحدّد مبلغ كل صفقة وعدد الصفقات المتزامنة." : "You set the size per trade and the number of concurrent positions."}</L>
              <L>{ar ? "أنت تستطيع إيقاف التداول الآلي في أي لحظة بزرّ واحد." : "You can stop auto-trading at any moment with one switch."}</L>
              <L>{ar ? "قرار الاستمرار ونتائجه عليك وحدك." : "The decision to continue, and its outcome, is yours alone."}</L>
            </ul>

            <S>{ar ? "لا ضمان للأرباح" : "No profit guarantee"}</S>
            <P>{ar
              ? "التداول بالرافعة ينطوي على مخاطر عالية وقد يؤدّي إلى خسارة رأس المال كلّه. الأرقام المعروضة نتائج سابقة حقيقية من سجلّ النظام، لكنها لا تضمن نتائج مستقبلية بأي حال."
              : "Leveraged trading carries high risk and can lose your entire capital. The figures shown are real past results from the system log, but they do not guarantee future performance in any way."}</P>

            <S>{ar ? "إساءة الاستخدام" : "Misuse"}</S>
            <P>{ar
              ? "يُمنع إعادة بيع الإشارات أو مشاركتها أو محاولة استخراجها آلياً. ونحتفظ بحقّ إيقاف أي حساب يخالف ذلك بلا استرداد."
              : "Reselling, sharing or scraping signals is prohibited. We reserve the right to suspend any account that does so, without refund."}</P>
          </>
        )}

        {tab === "privacy" && (
          <>
            <S>{ar ? "ما نجمعه" : "What we collect"}</S>
            <ul style={{ paddingInlineStart: 20, margin: 0 }}>
              <L>{ar ? "بريدك واسم المستخدم." : "Your email and username."}</L>
              <L>{ar ? "عنوان الـIP وبصمة الجهاز — لمنع استغلال التجربة المجانية." : "IP address and device fingerprint — to prevent free-trial abuse."}</L>
              <L>{ar ? "مفاتيح المنصّة مشفّرة، ولا تُعرض لأحد بعد الحفظ." : "Exchange keys, encrypted and never displayed again after saving."}</L>
              <L>{ar ? "سجلّ صفقاتك المنفَّذة عبر النظام." : "A record of trades executed through the system."}</L>
            </ul>

            <S>{ar ? "ما لا نفعله" : "What we don't do"}</S>
            <P>{ar
              ? "لا نبيع بياناتك ولا نشاركها مع مُعلنين. ولا نطّلع على مفاتيحك بعد تشفيرها. ولا نستخدم بياناتك لغير تشغيل الخدمة."
              : "We do not sell your data or share it with advertisers. We do not read your keys after encryption. We use your data only to run the service."}</P>

            <S>{ar ? "حذف حسابك" : "Deleting your account"}</S>
            <P>{ar
              ? "تستطيع طلب حذف حسابك وبياناتك من صفحة الدعم في أي وقت، وننفّذه خلال سبعة أيام."
              : "You can request deletion of your account and data from the support page at any time; we action it within seven days."}</P>
          </>
        )}

        {tab === "refund" && (
          <>
            <S>{ar ? "التجربة المجانية" : "The free trial"}</S>
            <P>{ar
              ? "أسبوع كامل بلا دفع. جرّب النظام قبل أن تشترك — فالتجربة هي ضمانك الأول."
              : "A full week with no payment. Try the system before subscribing — the trial is your first guarantee."}</P>

            <S>{ar ? "ضمان الاسترجاع" : "Money-back guarantee"}</S>
            <P>{ar
              ? "إن اشتركت وكانت نتيجتك سلبية خلال أول ١٤ يوماً، نُرجع اشتراكك كاملاً بشروط تضمن أنك شغّلت النظام فعلاً:"
              : "If you subscribe and your net result is negative within the first 14 days, we refund the full subscription, subject to conditions that confirm you actually ran the system:"}</P>
            <ul style={{ paddingInlineStart: 20, margin: 0 }}>
              <L>{ar ? "ربطتَ حساب منصّة فعلياً وفعّلتَ التداول الآلي." : "You linked a real exchange account and enabled auto-trading."}</L>
              <L>{ar ? "بقي التداول مفعّلاً عشرة أيام على الأقل." : "Auto-trading stayed on for at least ten days."}</L>
              <L>{ar ? "لم تُغلق صفقات يدوياً ولم تُعدّل إعدادات المخاطر أثناء المدّة." : "You did not close trades manually or change risk settings during the period."}</L>
              <L>{ar ? "الصافي سلبي فعلاً — نتحقّق منه من سجلّاتنا." : "The net result is genuinely negative — verified from our records."}</L>
            </ul>

            <S>{ar ? "متى لا يسري الضمان" : "When it doesn't apply"}</S>
            <P>{ar
              ? "إن لم تربط حساباً، أو أوقفت التداول مبكراً، أو تدخّلت يدوياً في الصفقات — فالنتيجة لا تعكس أداء النظام، ولا يسري الضمان."
              : "If you never linked an account, stopped trading early, or intervened manually — the result doesn't reflect the system's performance, and the guarantee doesn't apply."}</P>

            <S>{ar ? "الإلغاء" : "Cancellation"}</S>
            <P>{ar
              ? "تُلغي متى شئت، ويبقى وصولك حتى نهاية المدّة المدفوعة. لا تجديد تلقائي بلا علمك."
              : "Cancel whenever you like; access remains until the end of the paid period. No silent auto-renewal."}</P>
          </>
        )}
      </div>
    </div>
  );
}
