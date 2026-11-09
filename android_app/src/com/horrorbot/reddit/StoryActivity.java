package com.horrorbot.reddit;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.util.TypedValue;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;

/** Ecrã de leitura de uma história. */
public class StoryActivity extends Activity implements TextToSpeech.OnInitListener {
    private Store store;
    private Story story;
    private TextView body;
    private Button favButton, ttsButton;
    private TextToSpeech tts;
    private boolean ttsReady, speaking;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        store = new Store(this);
        String id = getIntent().getStringExtra("id");
        story = Store.CACHE.get(id);
        if (story == null) story = store.findFavorite(id);
        if (story == null) { // processo foi reiniciado e a história não está guardada
            finish();
            return;
        }
        store.markRead(story.id);
        setTitle("r/" + story.subreddit);

        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(MainActivity.BG);
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(dp(18), dp(16), dp(18), dp(48));
        scroll.addView(col);

        TextView title = new TextView(this);
        title.setText(story.title);
        title.setTextColor(MainActivity.ACCENT);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 23);
        title.setTypeface(android.graphics.Typeface.SERIF, android.graphics.Typeface.BOLD);
        col.addView(title);

        TextView meta = new TextView(this);
        String date = new SimpleDateFormat("dd/MM/yyyy", Locale.getDefault()).format(new Date(story.created * 1000L));
        meta.setText("u/" + story.author + "  ·  " + date + "\n" + MainActivity.meta(story, false)
                + "  ·  " + story.comments + " comentários");
        meta.setTextColor(MainActivity.MUTED);
        meta.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        meta.setPadding(0, dp(6), 0, dp(10));
        col.addView(meta);

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        favButton = button(buttons, "");
        updateFav();
        favButton.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                boolean now = store.toggleFavorite(story);
                updateFav();
                Toast.makeText(StoryActivity.this, now ? "Guardado para ler offline" : "Removido dos favoritos",
                        Toast.LENGTH_SHORT).show();
            }
        });
        ttsButton = button(buttons, "🔊 Ouvir");
        ttsButton.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { toggleSpeech(); }
        });
        button(buttons, "A−").setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { changeFont(-2); }
        });
        button(buttons, "A+").setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { changeFont(2); }
        });
        button(buttons, "Reddit").setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(story.url)));
            }
        });
        HorizontalScrollView hs = new HorizontalScrollView(this);
        hs.addView(buttons);
        col.addView(hs);

        body = new TextView(this);
        body.setText(story.body);
        body.setTextColor(MainActivity.TEXT);
        body.setTextSize(TypedValue.COMPLEX_UNIT_SP, store.fontSize());
        body.setLineSpacing(0, 1.35f);
        body.setTextIsSelectable(true);
        body.setPadding(0, dp(16), 0, 0);
        col.addView(body);

        setContentView(scroll);
    }

    private Button button(LinearLayout parent, String label) {
        Button b = new Button(this);
        b.setText(label);
        b.setAllCaps(false);
        parent.addView(b, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
        return b;
    }

    private void updateFav() {
        favButton.setText(store.isFavorite(story.id) ? "★ Favorito" : "☆ Favorito");
    }

    private void changeFont(float delta) {
        float size = Math.max(12f, Math.min(32f, store.fontSize() + delta));
        store.setFontSize(size);
        body.setTextSize(TypedValue.COMPLEX_UNIT_SP, size);
    }

    // ---------- leitura em voz alta ----------
    private void toggleSpeech() {
        if (speaking) {
            if (tts != null) tts.stop();
            speaking = false;
            ttsButton.setText("🔊 Ouvir");
            return;
        }
        if (tts == null) {
            ttsButton.setText("A preparar…");
            tts = new TextToSpeech(this, this);
            return;
        }
        if (ttsReady) speak();
    }

    @Override
    public void onInit(int result) {
        if (result != TextToSpeech.SUCCESS) {
            ttsButton.setText("🔊 Ouvir");
            Toast.makeText(this, "Leitura em voz alta indisponível neste aparelho.", Toast.LENGTH_LONG).show();
            return;
        }
        ttsReady = true;
        // As histórias estão em inglês.
        int lang = tts.setLanguage(Locale.US);
        if (lang == TextToSpeech.LANG_MISSING_DATA || lang == TextToSpeech.LANG_NOT_SUPPORTED) {
            tts.setLanguage(Locale.getDefault());
        }
        tts.setSpeechRate(0.95f);
        tts.setPitch(0.9f);
        speak();
    }

    private void speak() {
        speaking = true;
        ttsButton.setText("⏹ Parar");
        HashMap<String, String> params = new HashMap<String, String>();
        List<String> chunks = new ArrayList<String>();
        chunks.add(story.title + ".");
        chunks.addAll(split(story.body, 3000));
        for (int i = 0; i < chunks.size(); i++) {
            tts.speak(chunks.get(i), i == 0 ? TextToSpeech.QUEUE_FLUSH : TextToSpeech.QUEUE_ADD, params);
        }
    }

    /** Divide o texto em pedaços <= max, preferindo quebras de parágrafo ou de frase. */
    static List<String> split(String text, int max) {
        List<String> out = new ArrayList<String>();
        int start = 0;
        while (start < text.length()) {
            int end = Math.min(text.length(), start + max);
            if (end < text.length()) {
                int cut = text.lastIndexOf('\n', end);
                if (cut <= start) cut = text.lastIndexOf(". ", end);
                if (cut <= start) cut = text.lastIndexOf(' ', end);
                if (cut > start) end = cut + 1;
            }
            String part = text.substring(start, end).trim();
            if (part.length() > 0) out.add(part);
            start = end;
        }
        return out;
    }

    @Override
    protected void onDestroy() {
        if (tts != null) {
            tts.stop();
            tts.shutdown();
        }
        super.onDestroy();
    }

    int dp(float v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics());
    }
}
