import com.android.apksig.ApkSigner;
import com.android.apksig.ApkVerifier;

import java.io.File;
import java.io.FileInputStream;
import java.security.KeyStore;
import java.security.PrivateKey;
import java.security.cert.X509Certificate;
import java.util.Collections;

/** Assina um APK (esquema v2; Android 7.0+) com uma keystore PKCS12 e verifica o resultado. */
public class Sign {
    public static void main(String[] args) throws Exception {
        if (args.length != 5) {
            System.err.println("uso: Sign <entrada.apk> <saida.apk> <keystore.p12> <alias> <password>");
            System.exit(2);
        }
        char[] pass = args[4].toCharArray();
        KeyStore ks = KeyStore.getInstance("PKCS12");
        FileInputStream in = new FileInputStream(args[2]);
        ks.load(in, pass);
        in.close();
        PrivateKey key = (PrivateKey) ks.getKey(args[3], pass);
        X509Certificate cert = (X509Certificate) ks.getCertificate(args[3]);

        ApkSigner.SignerConfig signer =
                new ApkSigner.SignerConfig.Builder("CERT", key, Collections.singletonList(cert)).build();
        new ApkSigner.Builder(Collections.singletonList(signer))
                .setInputApk(new File(args[0]))
                .setOutputApk(new File(args[1]))
                .setMinSdkVersion(24)
                .setV1SigningEnabled(false)
                .setV2SigningEnabled(true)
                .build()
                .sign();

        ApkVerifier.Result r = new ApkVerifier.Builder(new File(args[1])).build().verify();
        System.out.println("verificado=" + r.isVerified() + " v1=" + r.isVerifiedUsingV1Scheme()
                + " v2=" + r.isVerifiedUsingV2Scheme());
        for (Object e : r.getErrors()) System.out.println("ERRO: " + e);
        if (!r.isVerified()) System.exit(1);
    }
}
