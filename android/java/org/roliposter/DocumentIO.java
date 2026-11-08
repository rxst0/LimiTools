package org.roliposter;

import android.content.Context;
import android.net.Uri;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/**
 * Reads and writes a file the user picked in Android's save / open screen (backup and restore).
 * The picker hands back a content:// address; this app only gets access to that one file.
 */
public class DocumentIO {
    private static final int MAX_BYTES = 5 * 1024 * 1024;

    public static boolean write(Context context, Uri uri, String text) {
        try (OutputStream out = context.getContentResolver().openOutputStream(uri, "wt")) {
            if (out == null) return false;
            out.write(text.getBytes(StandardCharsets.UTF_8));
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    /** The file's text, or null if it can't be read or is too big to be a backup. */
    public static String read(Context context, Uri uri) {
        try (InputStream in = context.getContentResolver().openInputStream(uri)) {
            if (in == null) return null;
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buffer = new byte[16384];
            int n;
            while ((n = in.read(buffer)) != -1) {
                if (out.size() + n > MAX_BYTES) return null;
                out.write(buffer, 0, n);
            }
            return new String(out.toByteArray(), StandardCharsets.UTF_8);
        } catch (Exception e) {
            return null;
        }
    }
}
