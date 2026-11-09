package com.horrorbot.reddit;

import org.json.JSONException;
import org.json.JSONObject;

/** Uma história recolhida do Reddit. */
public class Story {
    public String id;
    public String subreddit;
    public String title;
    public String author;
    public String body;
    public String url;
    public String flair;
    public int score;
    public int comments;
    public long created;
    public boolean nsfw;
    private int words = -1;

    public int words() {
        if (words < 0) {
            int count = 0;
            boolean inWord = false;
            for (int i = 0; i < body.length(); i++) {
                boolean ws = Character.isWhitespace(body.charAt(i));
                if (!ws && !inWord) count++;
                inWord = !ws;
            }
            words = count;
        }
        return words;
    }

    /** Minutos de leitura (~230 palavras por minuto). */
    public int readMinutes() {
        return Math.max(1, Math.round(words() / 230f));
    }

    /** Constrói a partir do campo "data" de um post do Reddit (kind t3). */
    public static Story fromReddit(JSONObject d) {
        Story s = new Story();
        s.id = d.optString("id");
        s.subreddit = d.optString("subreddit");
        s.title = d.optString("title").trim();
        String a = d.optString("author", "");
        s.author = a.length() == 0 ? "[deleted]" : a;
        s.body = d.optString("selftext", "").trim();
        s.url = "https://www.reddit.com" + d.optString("permalink", "");
        s.flair = d.isNull("link_flair_text") ? null : d.optString("link_flair_text", null);
        s.score = d.optInt("score");
        s.comments = d.optInt("num_comments");
        s.created = (long) d.optDouble("created_utc", 0);
        s.nsfw = d.optBoolean("over_18");
        return s;
    }

    public JSONObject toJson() {
        JSONObject o = new JSONObject();
        try {
            o.put("id", id);
            o.put("subreddit", subreddit);
            o.put("title", title);
            o.put("author", author);
            o.put("body", body);
            o.put("url", url);
            if (flair != null) o.put("flair", flair);
            o.put("score", score);
            o.put("comments", comments);
            o.put("created", created);
            o.put("nsfw", nsfw);
        } catch (JSONException e) {
            throw new RuntimeException(e);
        }
        return o;
    }

    public static Story fromJson(JSONObject o) {
        Story s = new Story();
        s.id = o.optString("id");
        s.subreddit = o.optString("subreddit");
        s.title = o.optString("title");
        s.author = o.optString("author");
        s.body = o.optString("body");
        s.url = o.optString("url");
        s.flair = o.has("flair") ? o.optString("flair") : null;
        s.score = o.optInt("score");
        s.comments = o.optInt("comments");
        s.created = o.optLong("created");
        s.nsfw = o.optBoolean("nsfw");
        return s;
    }
}
