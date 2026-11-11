package org.roliposter;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Sends one trade with the stored Roblox sign-in (see RobloxSession): the "Send trade" button on a trade ad
 * match, after the user confirmed it, and auto-send for trade ad alerts (off by default; its caps live in the
 * Python service). The cookie never leaves Java: callers pass Roblox user and asset IDs only.
 *
 * Steps: who am I (users/authenticated), can we trade (v2 can-trade-with), which copies (v2 tradableItems:
 * one instance per asset, never one on trade hold), then POST v2/trades/send. Nothing is ever offered in
 * Robux. At most 4 items a side.
 *
 * send() returns {"status": <code>, "tradeId": <id or 0>, "message": "<plain English>"}: 200 sent,
 * 0 not signed in, -1 network error, -2 bad input, -3 Roblox wants 2-step verification, -4 can't trade
 * with this player, -5 an item isn't available (not owned any more, or on hold), else Roblox's HTTP status.
 */
public class TradeSender {
    private static final int MAX_ITEMS = 4;
    private static final int MAX_PAGES = 60;
    private static final int MAX_BODY = 2 * 1024 * 1024;

    public static synchronized String send(Context context, long partnerId, String giveAssetIds, String getAssetIds,
                                           long partnerRobux) {
        try {
            List<String> give = ids(giveAssetIds), get = ids(getAssetIds);
            if (partnerId <= 0 || give == null || get == null || give.isEmpty() || get.size() + give.size() == 0
                    || give.size() > MAX_ITEMS || get.size() > MAX_ITEMS || partnerRobux < 0) {
                return result(-2, 0, "That trade isn't valid.");
            }
            String cookie = RobloxSession.get(context);
            if (cookie == null) return result(0, 0, "Sign in to Roblox in the Trades tab first.");

            Reply me = request(context, "GET", "https://users.roblox.com/v1/users/authenticated", null);
            if (me.status != 200) return failed(me, "Couldn't check your Roblox sign-in.");
            long myId = new JSONObject(me.body).getLong("id");
            if (myId == partnerId) return result(-2, 0, "That's your own ad.");

            Reply can = request(context, "GET", "https://trades.roblox.com/v2/users/" + partnerId + "/can-trade-with", null);
            if (can.status != 200) return failed(can, "Couldn't check whether you can trade with them.");
            if (!new JSONObject(can.body).optBoolean("canTrade", false)) {
                return result(-4, 0, "Roblox says you can't trade with this player right now (their trade "
                        + "settings, or yours).");
            }

            List<String> mine = instances(context, myId, give);
            if (mine == null) return result(-5, 0, "One of your items isn't available to trade (traded away, "
                    + "or on trade hold).");
            List<String> theirs = get.isEmpty() ? new ArrayList<>() : instances(context, partnerId, get);
            if (theirs == null) return result(-5, 0, "They don't have one of those items any more (or it's on "
                    + "hold).");

            JSONObject body = new JSONObject()
                    .put("senderOffer", new JSONObject().put("userId", myId).put("robux", 0)
                            .put("collectibleItemInstanceIds", new JSONArray(mine)))
                    .put("recipientOffer", new JSONObject().put("userId", partnerId).put("robux", partnerRobux)
                            .put("collectibleItemInstanceIds", new JSONArray(theirs)));
            Reply sent = request(context, "POST", "https://trades.roblox.com/v2/trades/send", body.toString());
            if (sent.challenge) {
                return result(-3, 0, "Roblox wants you to verify this trade (2-step verification). Send it on "
                        + "Roblox instead.");
            }
            if (sent.status == 200) {
                long tradeId = new JSONObject(sent.body).optLong("tradeId", 0);
                return result(200, tradeId, "Trade sent.");
            }
            return failed(sent, "Roblox didn't accept the trade.");
        } catch (Exception e) {
            return result(-1, 0, "Something went wrong sending the trade. Check your internet and try again.");
        }
    }

    /** One tradable copy per wanted asset ID (repeats = several copies), never one on hold; null if missing. */
    private static List<String> instances(Context context, long userId, List<String> assetIds) throws Exception {
        Map<String, Integer> need = new HashMap<>();
        for (String id : assetIds) need.put(id, need.getOrDefault(id, 0) + 1);
        Map<String, List<String>> found = new HashMap<>();
        String cursor = "";
        for (int page = 0; page < MAX_PAGES; page++) {
            String url = "https://trades.roblox.com/v2/users/" + userId + "/tradableItems?limit=50&sortBy=CreationTime"
                    + (cursor.isEmpty() ? "" : "&cursor=" + URLEncoder.encode(cursor, "UTF-8"));
            Reply reply = request(context, "GET", url, null);
            if (reply.status != 200) return null;
            JSONObject data = new JSONObject(reply.body);
            JSONArray items = data.optJSONArray("items");
            for (int i = 0; items != null && i < items.length(); i++) {
                JSONObject item = items.getJSONObject(i);
                JSONObject target = item.optJSONObject("itemTarget");
                String assetId = target == null ? "" : target.optString("targetId", "");
                if (!need.containsKey(assetId)) continue;
                JSONArray copies = item.optJSONArray("instances");
                for (int j = 0; copies != null && j < copies.length(); j++) {
                    JSONObject copy = copies.getJSONObject(j);
                    String instance = copy.optString("collectibleItemInstanceId", "");
                    if (instance.isEmpty() || copy.optBoolean("isOnHold", false)) continue;
                    found.computeIfAbsent(assetId, k -> new ArrayList<>()).add(instance);
                }
            }
            if (enough(need, found)) break;
            cursor = data.optString("nextPageCursor", "");
            if (cursor.isEmpty() || "null".equals(cursor)) break;
        }
        if (!enough(need, found)) return null;
        List<String> out = new ArrayList<>();
        for (String id : assetIds) {
            List<String> copies = found.get(id);
            out.add(copies.remove(0));
        }
        return out;
    }

    private static boolean enough(Map<String, Integer> need, Map<String, List<String>> found) {
        for (Map.Entry<String, Integer> e : need.entrySet()) {
            List<String> copies = found.get(e.getKey());
            if (copies == null || copies.size() < e.getValue()) return false;
        }
        return true;
    }

    private static List<String> ids(String csv) {
        List<String> out = new ArrayList<>();
        if (csv == null || csv.trim().isEmpty()) return out;
        for (String part : csv.split(",")) {
            String id = part.trim();
            if (!id.matches("^[0-9]{1,20}$")) return null;
            out.add(id);
        }
        return out;
    }

    private static class Reply {
        int status;
        String body = "";
        boolean challenge;
    }

    /** GET or POST (JSON) with the stored sign-in; fetches the CSRF token on a POST's first 403. */
    private static Reply request(Context context, String method, String url, String json) {
        Reply reply = new Reply();
        String cookie = RobloxSession.get(context);
        if (cookie == null) return reply;
        String csrf = "";
        for (int attempt = 0; attempt < 2; attempt++) {
            HttpURLConnection conn = null;
            try {
                conn = (HttpURLConnection) new URL(url).openConnection();
                conn.setRequestMethod(method);
                conn.setInstanceFollowRedirects(false);
                conn.setConnectTimeout(15000);
                conn.setReadTimeout(20000);
                conn.setRequestProperty("Cookie", RobloxSession.COOKIE + "=" + cookie);
                conn.setRequestProperty("Accept", "application/json");
                String agent = System.getProperty("http.agent");
                if (agent != null) conn.setRequestProperty("User-Agent", agent);
                if (json != null) {
                    conn.setDoOutput(true);
                    conn.setRequestProperty("Content-Type", "application/json");
                    if (!csrf.isEmpty()) conn.setRequestProperty("x-csrf-token", csrf);
                    conn.getOutputStream().write(json.getBytes(StandardCharsets.UTF_8));
                }
                int status = conn.getResponseCode();
                for (Map.Entry<String, List<String>> header : conn.getHeaderFields().entrySet()) {
                    if (header.getKey() == null || !header.getKey().equalsIgnoreCase("Set-Cookie")) continue;
                    for (String value : header.getValue()) {
                        if (value.trim().startsWith(RobloxSession.COOKIE + "=")) RobloxSession.rotated(context, value.trim());
                    }
                }
                String token = conn.getHeaderField("x-csrf-token");
                if (json != null && status == 403 && token != null && csrf.isEmpty()) {
                    csrf = token;
                    continue;
                }
                reply.status = status;
                reply.challenge = conn.getHeaderField("rblx-challenge-id") != null;
                InputStream in = status >= 400 ? conn.getErrorStream() : conn.getInputStream();
                reply.body = in == null ? "" : readBody(in);
                return reply;
            } catch (Exception e) {
                reply.status = -1;
                return reply;
            } finally {
                if (conn != null) conn.disconnect();
            }
        }
        reply.status = 403;
        return reply;
    }

    private static String failed(Reply reply, String what) {
        if (reply.status == -1) return result(-1, 0, what + " Check your internet and try again.");
        if (reply.status == 401) return result(401, 0, "Your Roblox sign-in has expired. Sign in again in the "
                + "Trades tab.");
        if (reply.status == 429) return result(429, 0, "Roblox says too many requests. Wait a minute and try again.");
        String detail = "";
        try {
            JSONArray errors = new JSONObject(reply.body).optJSONArray("errors");
            if (errors != null && errors.length() > 0) detail = errors.getJSONObject(0).optString("message", "");
        } catch (Exception ignored) {
        }
        return result(reply.status, 0, what + (detail.isEmpty() ? "" : " Roblox said: " + detail));
    }

    private static String readBody(InputStream in) throws Exception {
        try (InputStream stream = in) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buffer = new byte[16384];
            int n;
            while ((n = stream.read(buffer)) != -1) {
                if (out.size() + n > MAX_BODY) break;
                out.write(buffer, 0, n);
            }
            return new String(out.toByteArray(), StandardCharsets.UTF_8);
        }
    }

    private static String result(int status, long tradeId, String message) {
        try {
            return new JSONObject().put("status", status).put("tradeId", tradeId).put("message", message).toString();
        } catch (Exception e) {
            return "{\"status\": -1, \"tradeId\": 0, \"message\": \"\"}";
        }
    }
}
