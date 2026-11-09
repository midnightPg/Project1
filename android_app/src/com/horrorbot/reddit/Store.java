package com.horrorbot.reddit;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/** Persistência local: favoritos (lidos offline), histórias lidas e definições. */
public class Store {
    /** Histórias carregadas nesta sessão, para passar entre ecrãs sem limites de Intent. */
    public static final HashMap<String, Story> CACHE = new HashMap<String, Story>();

    private final SharedPreferences prefs;
    private LinkedHashMap<String, Story> favorites;

    public Store(Context ctx) {
        prefs = ctx.getSharedPreferences("horror", Context.MODE_PRIVATE);
    }

    // ---------- favoritos ----------
    private LinkedHashMap<String, Story> favs() {
        if (favorites == null) {
            favorites = new LinkedHashMap<String, Story>();
            try {
                JSONArray arr = new JSONArray(prefs.getString("favorites", "[]"));
                for (int i = 0; i < arr.length(); i++) {
                    Story s = Story.fromJson(arr.getJSONObject(i));
                    favorites.put(s.id, s);
                }
            } catch (JSONException ignored) {
            }
        }
        return favorites;
    }

    private void saveFavs() {
        JSONArray arr = new JSONArray();
        for (Story s : favs().values()) arr.put(s.toJson());
        prefs.edit().putString("favorites", arr.toString()).apply();
    }

    public boolean isFavorite(String id) {
        return favs().containsKey(id);
    }

    /** Alterna o favorito; devolve o novo estado. */
    public boolean toggleFavorite(Story s) {
        boolean now;
        if (favs().containsKey(s.id)) {
            favs().remove(s.id);
            now = false;
        } else {
            favs().put(s.id, s);
            now = true;
        }
        saveFavs();
        return now;
    }

    public List<Story> favoritesList() {
        List<Story> list = new ArrayList<Story>(favs().values());
        java.util.Collections.reverse(list); // mais recentes primeiro
        return list;
    }

    public Story findFavorite(String id) {
        return favs().get(id);
    }

    // ---------- lidas ----------
    public boolean isRead(String id) {
        return prefs.getStringSet("read", new HashSet<String>()).contains(id);
    }

    public void markRead(String id) {
        Set<String> set = new HashSet<String>(prefs.getStringSet("read", new HashSet<String>()));
        if (set.add(id)) prefs.edit().putStringSet("read", set).apply();
    }

    // ---------- definições ----------
    public int minScore() { return prefs.getInt("min_score", 50); }
    public int minWords() { return prefs.getInt("min_words", 300); }
    public boolean hideNsfw() { return prefs.getBoolean("hide_nsfw", false); }
    public float fontSize() { return prefs.getFloat("font_size", 18f); }
    public String clientId() { return prefs.getString("client_id", "").trim(); }

    public void setFilters(int minScore, int minWords, boolean hideNsfw) {
        prefs.edit().putInt("min_score", minScore).putInt("min_words", minWords)
                .putBoolean("hide_nsfw", hideNsfw).apply();
    }

    public void setFontSize(float size) { prefs.edit().putFloat("font_size", size).apply(); }

    public void setClientId(String id) { prefs.edit().putString("client_id", id.trim()).apply(); }

    public String deviceId() {
        String id = prefs.getString("device_id", null);
        if (id == null) {
            id = UUID.randomUUID().toString().replace("-", "").substring(0, 25);
            prefs.edit().putString("device_id", id).apply();
        }
        return id;
    }
}
