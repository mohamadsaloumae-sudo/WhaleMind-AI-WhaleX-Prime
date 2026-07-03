// منطق تفعيل إشعارات Push (تصل والتطبيق مغلق)
import { push } from "./api.js";

function urlB64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

export function pushSupported() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export async function isPushEnabled() {
  if (!pushSupported()) return false;
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    return !!sub && Notification.permission === "granted";
  } catch {
    return false;
  }
}

export async function enablePush() {
  if (!pushSupported()) {
    return { ok: false, error: "المتصفّح لا يدعم الإشعارات" };
  }
  // 1) طلب الإذن
  const perm = await Notification.requestPermission();
  if (perm !== "granted") {
    return { ok: false, error: "لم يُمنح إذن الإشعارات" };
  }
  try {
    // 2) المفتاح العام من الخادم
    const { public_key } = await push.publicKey();
    if (!public_key) return { ok: false, error: "لا مفتاح على الخادم" };
    // 3) الاشتراك عبر Service Worker
    const reg = await navigator.serviceWorker.ready;
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlB64ToUint8Array(public_key),
      });
    }
    // 4) إرسال الاشتراك للخادم
    await push.subscribe(sub.toJSON());
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message || "فشل الاشتراك" };
  }
}

export async function disablePush() {
  if (!pushSupported()) return { ok: false };
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (sub) {
      try { await push.unsubscribe(sub.toJSON()); } catch (e) { /* */ }
      await sub.unsubscribe();
    }
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}
