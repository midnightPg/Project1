package com.horrorbot.reddit;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ProgressBar;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;

public class MainActivity extends Activity {
    static final int BG = Color.rgb(13, 13, 13);
    static final int CARD = Color.rgb(26, 26, 26);
    static final int TEXT = Color.rgb(230, 230, 230);
    static final int MUTED = Color.rgb(140, 140, 140);
    static final int ACCENT = Color.rgb(198, 40, 40);

    static final String[] SUBREDDITS = {"nosleep", "shortscarystories", "LetsNotMeet",
            "Glitch_in_the_Matrix", "Thetruthishere", "TrueScaryStories", "creepyencounters",
            "scarystories"};
    static final String[] PERIOD_LABELS = {"Top de hoje", "Top da semana", "Top do mês", "Top do ano",
            "Top de sempre", "Em alta", "Mais recentes"};
    static final String[] PERIOD_SORT = {"top", "top", "top", "top", "top", "hot", "new"};
    static final String[] PERIOD_TIME = {"day", "week", "month", "year", "all", "", ""};

    private Store store;
    private Spinner subSpinner, periodSpinner;
    private TextView status;
    private ProgressBar progress;
    private Button moreButton;
    private final List<Story> stories = new ArrayList<Story>();
    private final HashSet<String> ids = new HashSet<String>();
    private StoryAdapter adapter;
    private String after;
    private boolean loading;
    private boolean showingFavorites;
    private int generation;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        store = new Store(this);
        setTitle("Histórias de Horror");

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);

        LinearLayout controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.HORIZONTAL);
        controls.setPadding(dp(8), dp(4), dp(8), dp(4));
        String[] subLabels = new String[SUBREDDITS.length + 1];
        subLabels[0] = "Todos os subreddits";
        for (int i = 0; i < SUBREDDITS.length; i++) subLabels[i + 1] = "r/" + SUBREDDITS[i];
        subSpinner = spinner(subLabels);
        periodSpinner = spinner(PERIOD_LABELS);
        periodSpinner.setSelection(1);
        controls.addView(subSpinner, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.2f));
        controls.addView(periodSpinner, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        root.addView(controls);

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setIndeterminate(true);
        progress.setVisibility(View.GONE);
        root.addView(progress, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(4)));

        status = new TextView(this);
        status.setTextColor(MUTED);
        status.setGravity(Gravity.CENTER);
        status.setPadding(dp(16), dp(24), dp(16), dp(24));
        status.setVisibility(View.GONE);
        root.addView(status);

        ListView list = new ListView(this);
        list.setDivider(null);
        list.setBackgroundColor(BG);
        list.setPadding(dp(8), 0, dp(8), dp(8));
        list.setClipToPadding(false);
        moreButton = new Button(this);
        moreButton.setText("Carregar mais");
        moreButton.setVisibility(View.GONE);
        moreButton.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { load(false); }
        });
        list.addFooterView(moreButton);
        adapter = new StoryAdapter();
        list.setAdapter(adapter);
        list.setOnItemClickListener(new AdapterView.OnItemClickListener() {
            public void onItemClick(AdapterView<?> parent, View view, int position, long id) {
                if (position >= stories.size()) return;
                Story s = stories.get(position);
                Store.CACHE.put(s.id, s);
                startActivity(new Intent(MainActivity.this, StoryActivity.class).putExtra("id", s.id));
            }
        });
        root.addView(list, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        setContentView(root);

        AdapterView.OnItemSelectedListener reload = new AdapterView.OnItemSelectedListener() {
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                showingFavorites = false;
                load(true);
            }
            public void onNothingSelected(AdapterView<?> parent) { }
        };
        subSpinner.setOnItemSelectedListener(reload);
        periodSpinner.setOnItemSelectedListener(reload);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (showingFavorites) showFavorites();
        else adapter.notifyDataSetChanged(); // atualiza marcas de lido/favorito
    }

    private Spinner spinner(String[] items) {
        Spinner s = new Spinner(this);
        ArrayAdapter<String> a = new ArrayAdapter<String>(this, android.R.layout.simple_spinner_item, items);
        a.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        s.setAdapter(a);
        return s;
    }

    private String selectedSubs() {
        int i = subSpinner.getSelectedItemPosition();
        if (i > 0) return SUBREDDITS[i - 1];
        StringBuilder sb = new StringBuilder();
        for (String s : SUBREDDITS) {
            if (sb.length() > 0) sb.append('+');
            sb.append(s);
        }
        return sb.toString();
    }

    private void load(final boolean reset) {
        if (reset) {
            generation++;
            stories.clear();
            ids.clear();
            after = null;
            adapter.notifyDataSetChanged();
        } else if (loading || after == null) {
            return;
        }
        final int gen = generation;
        final String subs = selectedSubs();
        final int p = periodSpinner.getSelectedItemPosition();
        final String afterParam = after;
        loading = true;
        progress.setVisibility(View.VISIBLE);
        status.setVisibility(View.GONE);
        moreButton.setVisibility(View.GONE);

        new Thread(new Runnable() {
            public void run() {
                RedditApi.Page page = null;
                String error = null;
                try {
                    page = RedditApi.fetch(store, subs, PERIOD_SORT[p], PERIOD_TIME[p], afterParam);
                } catch (Exception e) {
                    error = e.getMessage() != null ? e.getMessage() : e.toString();
                    if (e instanceof java.net.UnknownHostException) error = "Sem ligação à Internet.";
                }
                final RedditApi.Page result = page;
                final String err = error;
                runOnUiThread(new Runnable() {
                    public void run() { onLoaded(gen, result, err); }
                });
            }
        }).start();
    }

    private void onLoaded(int gen, RedditApi.Page page, String error) {
        if (gen != generation || showingFavorites) return; // pedido antigo
        loading = false;
        progress.setVisibility(View.GONE);
        if (error != null) {
            showStatus(error + "\n\nToca para tentar de novo.");
            status.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { load(stories.isEmpty()); }
            });
            if (!stories.isEmpty()) moreButton.setVisibility(View.VISIBLE);
            return;
        }
        status.setOnClickListener(null);
        for (Story s : page.stories) {
            if (ids.add(s.id)) stories.add(s);
        }
        after = page.after;
        adapter.notifyDataSetChanged();
        moreButton.setVisibility(after != null ? View.VISIBLE : View.GONE);
        if (stories.isEmpty()) {
            if (after != null) {
                // Nenhum post desta página passou nos filtros: tenta a próxima automaticamente.
                load(false);
                return;
            }
            showStatus("Nenhuma história encontrada com os filtros atuais.");
        }
    }

    private void showStatus(String msg) {
        status.setText(msg);
        status.setVisibility(View.VISIBLE);
    }

    private void showFavorites() {
        showingFavorites = true;
        generation++;
        loading = false;
        progress.setVisibility(View.GONE);
        moreButton.setVisibility(View.GONE);
        stories.clear();
        ids.clear();
        for (Story s : store.favoritesList()) {
            stories.add(s);
            ids.add(s.id);
        }
        adapter.notifyDataSetChanged();
        setTitle("★ Favoritos");
        if (stories.isEmpty()) showStatus("Ainda não tens favoritos.\nAbre uma história e toca em ☆.");
        else status.setVisibility(View.GONE);
    }

    // ---------- menu ----------
    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        menu.add(0, 1, 0, "Atualizar").setShowAsAction(MenuItem.SHOW_AS_ACTION_IF_ROOM);
        menu.add(0, 2, 0, "Favoritos").setShowAsAction(MenuItem.SHOW_AS_ACTION_IF_ROOM);
        menu.add(0, 3, 0, "Filtros");
        menu.add(0, 4, 0, "Client ID do Reddit");
        menu.add(0, 5, 0, "Sobre");
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        switch (item.getItemId()) {
            case 1:
                showingFavorites = false;
                setTitle("Histórias de Horror");
                load(true);
                return true;
            case 2:
                if (showingFavorites) {
                    showingFavorites = false;
                    setTitle("Histórias de Horror");
                    load(true);
                } else {
                    showFavorites();
                }
                return true;
            case 3:
                filtersDialog();
                return true;
            case 4:
                clientIdDialog();
                return true;
            case 5:
                new AlertDialog.Builder(this).setTitle("Histórias de Horror")
                        .setMessage("Lê histórias de horror de r/nosleep, r/shortscarystories, "
                                + "r/LetsNotMeet e outros.\n\nAs histórias pertencem aos seus autores. "
                                + "Pede autorização antes de as republicar.\n\nVersão 1.0")
                        .setPositiveButton("OK", null).show();
                return true;
        }
        return super.onOptionsItemSelected(item);
    }

    private EditText numberField(LinearLayout parent, String label, int value) {
        TextView l = new TextView(this);
        l.setText(label);
        parent.addView(l);
        EditText e = new EditText(this);
        e.setInputType(InputType.TYPE_CLASS_NUMBER);
        e.setText(String.valueOf(value));
        parent.addView(e);
        return e;
    }

    private void filtersDialog() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(20), dp(8), dp(20), 0);
        final EditText score = numberField(box, "Score mínimo (upvotes)", store.minScore());
        final EditText words = numberField(box, "Número mínimo de palavras", store.minWords());
        final CheckBox nsfw = new CheckBox(this);
        nsfw.setText("Esconder histórias NSFW");
        nsfw.setChecked(store.hideNsfw());
        box.addView(nsfw);
        new AlertDialog.Builder(this).setTitle("Filtros").setView(box)
                .setPositiveButton("Guardar", new DialogInterface.OnClickListener() {
                    public void onClick(DialogInterface d, int w) {
                        store.setFilters(parse(score, 50), parse(words, 300), nsfw.isChecked());
                        if (!showingFavorites) load(true);
                    }
                })
                .setNegativeButton("Cancelar", null).show();
    }

    private void clientIdDialog() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(20), dp(8), dp(20), 0);
        TextView help = new TextView(this);
        help.setText("Opcional. Se o Reddit bloquear os pedidos, cria uma app do tipo \"installed app\" em "
                + "reddit.com/prefs/apps (redirect uri: http://localhost) e cola aqui o Client ID. "
                + "Deixa vazio para usar o modo anónimo.");
        box.addView(help);
        final EditText field = new EditText(this);
        field.setSingleLine(true);
        field.setText(store.clientId());
        box.addView(field);
        new AlertDialog.Builder(this).setTitle("Client ID do Reddit").setView(box)
                .setPositiveButton("Guardar", new DialogInterface.OnClickListener() {
                    public void onClick(DialogInterface d, int w) {
                        store.setClientId(field.getText().toString());
                        Toast.makeText(MainActivity.this, "Guardado", Toast.LENGTH_SHORT).show();
                        if (!showingFavorites) load(true);
                    }
                })
                .setNegativeButton("Cancelar", null).show();
    }

    private static int parse(EditText e, int def) {
        try {
            return Math.max(0, Integer.parseInt(e.getText().toString().trim()));
        } catch (NumberFormatException ex) {
            return def;
        }
    }

    // ---------- lista ----------
    int dp(float v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics());
    }

    static String compact(int n) {
        if (n >= 1000) {
            float k = n / 1000f;
            return (k >= 10 ? String.valueOf(Math.round(k)) : String.format("%.1f", k)) + "k";
        }
        return String.valueOf(n);
    }

    static String meta(Story s, boolean fav) {
        return "r/" + s.subreddit + "  ·  ▲ " + compact(s.score) + "  ·  " + s.words() + " palavras  ·  "
                + s.readMinutes() + " min" + (s.nsfw ? "  ·  NSFW" : "") + (fav ? "  ·  ★" : "");
    }

    private class StoryAdapter extends BaseAdapter {
        public int getCount() { return stories.size(); }
        public Object getItem(int i) { return stories.get(i); }
        public long getItemId(int i) { return i; }

        public View getView(int position, View convert, ViewGroup parent) {
            LinearLayout card;
            TextView title, meta;
            if (convert instanceof LinearLayout) {
                card = (LinearLayout) convert;
                title = (TextView) card.getChildAt(0);
                meta = (TextView) card.getChildAt(1);
            } else {
                card = new LinearLayout(MainActivity.this);
                card.setOrientation(LinearLayout.VERTICAL);
                card.setPadding(dp(14), dp(12), dp(14), dp(12));
                title = new TextView(MainActivity.this);
                title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 17);
                title.setTypeface(Typeface.DEFAULT_BOLD);
                meta = new TextView(MainActivity.this);
                meta.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
                meta.setTextColor(MUTED);
                meta.setPadding(0, dp(4), 0, 0);
                card.addView(title);
                card.addView(meta);
                card.setLayoutParams(new ListView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));
            }
            Story s = stories.get(position);
            boolean read = store.isRead(s.id);
            card.setBackgroundColor(position % 2 == 0 ? CARD : BG);
            title.setText(s.title);
            title.setTextColor(read ? MUTED : TEXT);
            meta.setText(meta(s, store.isFavorite(s.id)));
            return card;
        }
    }
}
