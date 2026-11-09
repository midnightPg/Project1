package com.horrorbot.reddit;

import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.List;

/**
 * Acesso à API do Reddit.
 * Sem Client ID usa os endpoints públicos .json; com Client ID (app do tipo
 * "installed app" em reddit.com/prefs/apps) usa OAuth em oauth.reddit.com.
 */
public class RedditApi {
    static final String USER_AGENT = "android:com.horrorbot.reddit:v1.0 (personal use)";
    private static final String[] EXCLUDED_FLAIRS = {"meta", "announcement", "mod post", "discussion"};

    private static String token;
    private static long tokenExpires;
    private static String tokenClientId;

    public static class Page {
        public final List<Story> stories = new ArrayList<Story>();
        public String after;
        public int seen;
    }

    public static Page fetch(Store store, String subs, String sort, String time, String after)
            throws IOException {
        StringBuilder q = new StringBuilder("limit=100&raw_json=1");
        if ("top".equals(sort)) q.append("&t=").append(time);
        if (after != null) q.append("&after=").append(URLEncoder.encode(after, "UTF-8"));

        String clientId = store.clientId();
        String url;
        String auth = null;
        if (clientId.length() > 0) {
            auth = "bearer " + getToken(clientId, store.deviceId());
            url = "https://oauth.reddit.com/r/" + subs + "/" + sort + "?" + q;
        } else {
            url = "https://www.reddit.com/r/" + subs + "/" + sort + ".json?" + q;
        }

        String text = request(url, "GET", auth, null);
        Page page = new Page();
        try {
            JSONObject data = new JSONObject(text).getJSONObject("data");
            page.after = data.isNull("after") ? null : data.optString("after", null);
            JSONArray children = data.getJSONArray("children");
            int minScore = store.minScore(), minWords = store.minWords();
            boolean hideNsfw = store.hideNsfw();
            for (int i = 0; i < children.length(); i++) {
                JSONObject child = children.getJSONObject(i);
                if (!"t3".equals(child.optString("kind"))) continue;
                page.seen++;
                JSONObject d = child.getJSONObject("data");
                Story s = Story.fromReddit(d);
                if (accept(d, s, minScore, minWords, hideNsfw)) page.stories.add(s);
            }
        } catch (JSONException e) {
            throw new IOException("Resposta inesperada do Reddit (pode estar a bloquear pedidos anónimos — "
                    + "define um Client ID no menu).");
        }
        return page;
    }

    static boolean accept(JSONObject d, Story s, int minScore, int minWords, boolean hideNsfw) {
        if (d.optBoolean("stickied")) return false;
        if (!d.optBoolean("is_self", true)) return false;
        if (s.body.length() == 0 || "[removed]".equals(s.body) || "[deleted]".equals(s.body)) return false;
        if (!d.isNull("removed_by_category")) return false;
        if (hideNsfw && s.nsfw) return false;
        if (s.flair != null) {
            String f = s.flair.trim().toLowerCase();
            for (String ex : EXCLUDED_FLAIRS) if (ex.equals(f)) return false;
        }
        if (s.score < minScore) return false;
        return s.words() >= minWords;
    }

    private static synchronized String getToken(String clientId, String deviceId) throws IOException {
        if (token != null && clientId.equals(tokenClientId) && System.currentTimeMillis() < tokenExpires) {
            return token;
        }
        String basic = "Basic " + Base64.encodeToString((clientId + ":").getBytes("UTF-8"), Base64.NO_WRAP);
        String body = "grant_type=" + URLEncoder.encode("https://oauth.reddit.com/grants/installed_client", "UTF-8")
                + "&device_id=" + deviceId;
        String text = request("https://www.reddit.com/api/v1/access_token", "POST", basic, body);
        try {
            JSONObject o = new JSONObject(text);
            if (!o.has("access_token")) throw new IOException("Client ID inválido: " + o.optString("error", text));
            token = o.getString("access_token");
            tokenClientId = clientId;
            tokenExpires = System.currentTimeMillis() + (o.optLong("expires_in", 3600) - 60) * 1000L;
            return token;
        } catch (JSONException e) {
            throw new IOException("Falha ao obter token OAuth.");
        }
    }

    private static String request(String url, String method, String auth, String body) throws IOException {
        IOException last = null;
        for (int attempt = 0; attempt < 3; attempt++) {
            HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
            try {
                c.setRequestMethod(method);
                c.setConnectTimeout(20000);
                c.setReadTimeout(30000);
                c.setRequestProperty("User-Agent", USER_AGENT);
                c.setRequestProperty("Accept", "application/json");
                if (auth != null) c.setRequestProperty("Authorization", auth);
                if (body != null) {
                    c.setDoOutput(true);
                    c.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
                    OutputStream os = c.getOutputStream();
                    os.write(body.getBytes("UTF-8"));
                    os.close();
                }
                int code = c.getResponseCode();
                if (code == 429 || code >= 500) {
                    last = new IOException("O Reddit está ocupado (HTTP " + code + "). Tenta daqui a pouco.");
                    sleep(2000L << attempt);
                    continue;
                }
                if (code == 403) {
                    throw new IOException("O Reddit recusou o pedido (HTTP 403). Subreddit privado, ou pedidos "
                            + "anónimos bloqueados — define um Client ID no menu.");
                }
                if (code == 404) throw new IOException("Subreddit não encontrado (HTTP 404).");
                if (code >= 400) throw new IOException("Erro HTTP " + code);
                return readAll(c.getInputStream());
            } finally {
                c.disconnect();
            }
        }
        throw last;
    }

    private static String readAll(InputStream in) throws IOException {
        BufferedReader r = new BufferedReader(new InputStreamReader(in, "UTF-8"));
        StringBuilder sb = new StringBuilder();
        char[] buf = new char[8192];
        int n;
        while ((n = r.read(buf)) > 0) sb.append(buf, 0, n);
        r.close();
        return sb.toString();
    }

    private static void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException ignored) {
        }
    }
}
