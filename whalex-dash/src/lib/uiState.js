/**
 * 🎛️ حالة الواجهة المشتركة — طيّ القائمة وعرضها.
 *    نستخدم حدث نافذة بدل سياق React كي يُستعمل من أي مكوّن بلا تمرير.
 */
const KEY_C = "wx_sb_collapsed";
const KEY_W = "wx_sb_width";

export function isCollapsed() {
  return localStorage.getItem(KEY_C) === "1";
}

export function setCollapsed(v) {
  localStorage.setItem(KEY_C, v ? "1" : "0");
  document.querySelector(".app-shell")?.classList.toggle("wx-collapsed", !!v);
  window.dispatchEvent(new Event("wx-sidebar"));
}

export function toggleSidebar() {
  setCollapsed(!isCollapsed());
}

export function getWidth() {
  return parseInt(localStorage.getItem(KEY_W) || "0", 10) || 0;
}

export function setWidth(px) {
  const w = Math.max(150, Math.min(420, px));
  localStorage.setItem(KEY_W, String(w));
  document.documentElement.style.setProperty("--sidebar-w", w + "px");
}

/** يُستدعى عند الإقلاع — يُعيد ما حفظه المستخدم */
export function applyUI() {
  if (isCollapsed()) {
    document.querySelector(".app-shell")?.classList.add("wx-collapsed");
  }
  const w = getWidth();
  if (w) document.documentElement.style.setProperty("--sidebar-w", w + "px");
}
