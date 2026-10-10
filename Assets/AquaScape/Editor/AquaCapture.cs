using System.IO;
using UnityEditor;
using UnityEngine;

namespace AquaScape.EditorTools
{
    /// <summary>
    /// Renders the main camera (including the screen-space-camera UI) into a
    /// 1920x1080 render texture and saves it under Captures/. Used for the
    /// progress screenshots and works at any Game view size.
    /// </summary>
    public static class AquaCapture
    {
        [MenuItem("AquaScape/Capture 1080p Screenshot")]
        public static void CaptureMenu() => Capture("capture_" + System.DateTime.Now.ToString("HHmmss"));

        public static string Capture(string name, int width = 1920, int height = 1080)
        {
            var cam = Camera.main;
            if (cam == null) return "no camera";
            var rt = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32) { antiAliasing = 1 };
            var prevTarget = cam.targetTexture;
            var prevActive = RenderTexture.active;

            cam.targetTexture = rt;
            cam.Render();
            RenderTexture.active = rt;
            var tex = new Texture2D(width, height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, width, height), 0, 0);
            tex.Apply();

            cam.targetTexture = prevTarget;
            RenderTexture.active = prevActive;
            rt.Release();
            Object.DestroyImmediate(rt);

            Directory.CreateDirectory("Captures");
            string path = Path.Combine("Captures", name + ".png");
            File.WriteAllBytes(path, tex.EncodeToPNG());
            Object.DestroyImmediate(tex);
            return Path.GetFullPath(path);
        }
    }
}
