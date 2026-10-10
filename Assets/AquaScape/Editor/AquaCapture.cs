using System.IO;
using UnityEditor;
using UnityEngine;

namespace AquaScape.EditorTools
{
    // takes a 1080p screenshot of the main camera and saves it in the captures folder
    public static class AquaCapture
    {
        [MenuItem("AquaScape/Capture 1080p Screenshot")]
        public static void CaptureMenu() => Capture("capture_" + System.DateTime.Now.ToString("HHmmss"));

        // renders the camera into a texture and saves it as a png
        public static string Capture(string name, int width = 1920, int height = 1080)
        {
            var cam = Camera.main;
            if (cam == null) return "no camera";
            var rt = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32) { antiAliasing = 1 };
            var prevTarget = cam.targetTexture;
            var prevActive = RenderTexture.active;

            // draw the camera and read back the pixels
            cam.targetTexture = rt;
            cam.Render();
            RenderTexture.active = rt;
            var tex = new Texture2D(width, height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, width, height), 0, 0);
            tex.Apply();

            // put the camera back how it was
            cam.targetTexture = prevTarget;
            RenderTexture.active = prevActive;
            rt.Release();
            Object.DestroyImmediate(rt);

            // save the file
            Directory.CreateDirectory("Captures");
            string path = Path.Combine("Captures", name + ".png");
            File.WriteAllBytes(path, tex.EncodeToPNG());
            Object.DestroyImmediate(tex);
            return Path.GetFullPath(path);
        }
    }
}
