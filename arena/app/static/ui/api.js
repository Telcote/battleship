// С телом — POST, без тела — GET.
export async function api(path, body) {
  const init = { headers: { Accept: "application/json" } };
  if (body !== undefined) {
    init.method = "POST";
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const response = await fetch(path, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail ?? `${response.status} ${response.statusText}`);
  return payload;
}
