# 📱 Histórias de Horror — app Android

App Android para ler histórias de horror do Reddit no telemóvel
(r/nosleep, r/shortscarystories, r/LetsNotMeet, r/Glitch_in_the_Matrix, ...).
Usa os mesmos filtros do bot em Python (`../reddit_horror_bot`).

**APK pronto:** [`release/historias-de-horror-1.0.apk`](release/historias-de-horror-1.0.apk) (~26 KB, Android 7.0 ou superior)

## Funcionalidades
- Lista de histórias por subreddit (ou todos juntos) e por período: top de hoje/semana/mês/ano/sempre, em alta, recentes
- Filtros configuráveis: score mínimo, número mínimo de palavras, esconder NSFW
- Ecrã de leitura com tema escuro, tamanho de letra ajustável e tempo de leitura estimado
- ★ Favoritos guardados no telemóvel para **ler offline**
- 🔊 Leitura em voz alta (texto-para-voz do Android, em inglês)
- Histórias já lidas ficam a cinzento
- Botão para abrir a história original no Reddit

## Instalar no telemóvel
1. Descarrega o ficheiro `.apk` para o telemóvel.
2. Abre-o. O Android vai pedir para permitires a instalação de "apps desconhecidas" para o browser
   ou gestor de ficheiros: aceita.
3. Se o Play Protect avisar que a app é desconhecida, escolhe **Instalar mesmo assim**
   (a app não está na Play Store, por isso o aviso é normal).

## Se o Reddit bloquear os pedidos
O Reddit às vezes recusa pedidos anónimos. Nesse caso:
1. Vai a <https://www.reddit.com/prefs/apps> → **create app** → tipo **installed app**,
   redirect uri `http://localhost`.
2. Copia o Client ID (o código por baixo do nome da app).
3. Na app: menu ⋮ → **Client ID do Reddit** → cola e guarda.

## Compilar o APK
Não precisa do Android SDK nem do Android Studio — só de **JDK 17+** e **Python 3**:

```bash
cd android_app
python3 build_tools/build_apk.py
# → dist/historias-de-horror-1.0.apk
```

O script descarrega do Maven Central o `dx` (gera o código Android), o `apksig` (assina o APK) e
a API do Android só para compilar. O `AndroidManifest.xml` e o `resources.arsc` são escritos
diretamente em formato binário pelo próprio script, e o ícone é desenhado em código.

Na primeira compilação é criada a chave de assinatura `release.p12` (não vai para o git).
**Guarda-a:** para instalar uma versão nova por cima da antiga tens de assinar com a mesma chave;
se a perderes, desinstala a app antes de instalar a nova versão.
