package org.roliposter;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Notable followers and friend requests (Settings, off by default): "Verified user X sent you a friend
 * request", "X (12.4K followers) followed you". TradeWatcher calls check() from the background service.
 * Read-only: it uses RobloxApi's friend_requests / followers / follower_count / user requests.
 * The first check only remembers who's already there, so it never floods you with old ones.
 */
public class SocialAlerts {
    public static final String CHANNEL = "social";
    private static final String RULES_FILE = "social_alerts_rules.json";
    private static final String PREFS = "roliposter_social";
    private static final int MAX_NEW_PER_CHECK = 8;   // each new person costs two lookups
    private static final int MAX_SEEN = 500;
    private static final Pattern SAFE_NAME = Pattern.compile("^[A-Za-z0-9_ .]{1,40}$");

    public static volatile int notifiedCount = 0;

    /** Called by the app: {"enabled", "user_id", "min_followers", "verified", "friend_requests", "follows"}. */
    public static synchronized void setRules(Context context, String json) {
        File target = new File(context.getApplicationContext().getFilesDir(), RULES_FILE);
        try {
            String text = new JSONObject(json).toString();
            File tmp = new File(target.getPath() + ".tmp");
            try (FileOutputStream out = new FileOutputStream(tmp)) {
                out.write(text.getBytes(StandardCharsets.UTF_8));
            }
            if (!tmp.renameTo(target)) {
                target.delete();
                tmp.renameTo(target);
            }
        } catch (Exception e) {
            target.delete();  // bad rules: off
        }
    }

    static JSONObject rules(Context context) {
        File f = new File(context.getApplicationContext().getFilesDir(), RULES_FILE);
        try {
            return f.exists() ? new JSONObject(new String(Files.readAllBytes(f.toPath()), StandardCharsets.UTF_8)) : null;
        } catch (Exception e) {
            return null;
        }
    }

    /** Whether new-trade / accepted-trade alerts are on (false when the service runs only for these). */
    public static boolean tradeAlertsWanted(Context context) {
        JSONObject r = rules(context);
        return r == null || r.optBoolean("trade_alerts", true);
    }

    public static boolean enabled(Context context) {
        JSONObject r = rules(context);
        return r != null && r.optBoolean("enabled", false);
    }

    @SuppressWarnings("deprecation")
    private static SharedPreferences prefs(Context context) {
        return context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_MULTI_PROCESS);
    }

    /** One round of checks (background thread). */
    static void check(Context context) {
        JSONObject r = rules(context);
        if (r == null || !r.optBoolean("enabled", false)) return;
        if (r.optBoolean("friend_requests", true)) {
            scan(context, r, "requests", RobloxApi.fetch(context, "friend_requests", "", ""), "sent you a friend request");
        }
        long me = r.optLong("user_id");
        if (r.optBoolean("follows", true) && me > 0) {
            scan(context, r, "followers", RobloxApi.fetch(context, "followers", String.valueOf(me), ""), "followed you");
        }
    }

    private static void scan(Context context, JSONObject rules, String kind, String reply, String action) {
        List<long[]> people = new ArrayList<>();
        List<String> names = new ArrayList<>();
        try {
            JSONObject r = new JSONObject(reply);
            if (r.getInt("status") != 200) return;
            JSONArray data = new JSONObject(r.getString("body")).getJSONArray("data");
            for (int i = 0; i < data.length(); i++) {
                JSONObject p = data.getJSONObject(i);
                long id = p.optLong("id");
                if (id <= 0) continue;
                people.add(new long[]{id});
                String name = p.optString("name", "");
                names.add(SAFE_NAME.matcher(name).matches() ? name : "Someone");
            }
        } catch (Exception e) {
            return;
        }
        SharedPreferences prefs = prefs(context);
        Set<String> seen = new HashSet<>(prefs.getStringSet("seen_" + kind, new HashSet<String>()));
        boolean firstRun = !prefs.getBoolean("seeded_" + kind, false);
        int looked = 0;
        for (int i = 0; i < people.size(); i++) {
            String id = String.valueOf(people.get(i)[0]);
            if (seen.contains(id)) continue;
            seen.add(id);
            if (firstRun || looked >= MAX_NEW_PER_CHECK) continue;
            looked++;
            notifyIfNotable(context, rules, id, names.get(i), action);
        }
        if (seen.size() > MAX_SEEN) {
            Set<String> keep = new HashSet<>();
            for (long[] p : people) keep.add(String.valueOf(p[0]));
            seen = keep;
        }
        prefs.edit().putStringSet("seen_" + kind, seen).putBoolean("seeded_" + kind, true).commit();
    }

    private static void notifyIfNotable(Context context, JSONObject rules, String id, String name, String action) {
        boolean verified = false;
        long followers = -1;
        try {
            JSONObject user = new JSONObject(RobloxApi.fetch(context, "user", id, ""));
            if (user.getInt("status") == 200) {
                JSONObject body = new JSONObject(user.getString("body"));
                verified = body.optBoolean("hasVerifiedBadge", false);
                String real = body.optString("name", "");
                if (SAFE_NAME.matcher(real).matches()) name = real;
            }
            JSONObject count = new JSONObject(RobloxApi.fetch(context, "follower_count", id, ""));
            if (count.getInt("status") == 200) followers = new JSONObject(count.getString("body")).optLong("count", -1);
        } catch (Exception e) {
            return;
        }
        long min = rules.optLong("min_followers", 1000);
        boolean byFollowers = min > 0 && followers >= min;
        boolean byBadge = verified && rules.optBoolean("verified", true);
        if (!byFollowers && !byBadge) return;
        String who = (verified ? "Verified user " : "") + name
                + (followers >= 0 ? " (" + shortCount(followers) + " followers)" : "");
        show(context, (int) (5000 + Long.parseLong(id) % 100000), who + " " + action,
                "Tap to open their Roblox profile.", "https://www.roblox.com/users/" + id + "/profile");
    }

    static String shortCount(long n) {
        if (n >= 1_000_000) return trim(n / 1_000_000.0) + "M";
        if (n >= 1_000) return trim(n / 1_000.0) + "K";
        return String.valueOf(n);
    }

    private static String trim(double v) {
        String s = String.format(java.util.Locale.US, "%.1f", v);
        return s.endsWith(".0") ? s.substring(0, s.length() - 2) : s;
    }

    private static void show(Context context, int notificationId, String title, String text, String url) {
        NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager == null) return;
        manager.createNotificationChannel(new NotificationChannel(CHANNEL, "Notable followers and friend requests",
                NotificationManager.IMPORTANCE_HIGH));
        Intent open = new Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        PendingIntent pending = PendingIntent.getActivity(context, notificationId, open,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        manager.notify(notificationId, new Notification.Builder(context, CHANNEL)
                .setContentTitle(title)
                .setContentText(text)
                .setSmallIcon(context.getApplicationInfo().icon)
                .setContentIntent(pending)
                .setAutoCancel(true)
                .build());
        notifiedCount++;
    }
}
