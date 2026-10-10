using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace AquaScape.EditorTools
{
    // sets the same import settings on every sprite in the art folder
    // pivots and borders can be changed by the sprite meta json files next to the art
    public class AquaSpriteImporter : AssetPostprocessor
    {
        const string ArtRoot = "Assets/AquaScape/Art/";
        // one tile is one world unit
        public const float PixelsPerUnit = 128f;

        // character frames are 192 by 224 with the feet 17 pixels above the bottom
        static readonly Vector2 CharacterPivot = new Vector2(0.5f, 17f / 224f);

        // one sprite entry from the json file
        [System.Serializable] class Entry { public float[] pivot; public float[] border; }

        static Dictionary<string, Entry> s_meta;

        void OnPreprocessTexture()
        {
            if (!assetPath.StartsWith(ArtRoot)) return;
            var importer = (TextureImporter)assetImporter;
            string rel = assetPath.Substring(ArtRoot.Length);

            // basic sprite settings
            importer.textureType = TextureImporterType.Sprite;
            importer.spriteImportMode = SpriteImportMode.Single;
            importer.spritePixelsPerUnit = PixelsPerUnit;
            importer.filterMode = FilterMode.Bilinear;
            importer.textureCompression = TextureImporterCompression.Uncompressed;
            importer.alphaIsTransparency = true;
            importer.mipmapEnabled = rel.StartsWith("FX/cloud") || rel.StartsWith("Props/") || rel.StartsWith("Backgrounds/backdrop") || rel.StartsWith("Scenery/");
            importer.wrapMode = TextureWrapMode.Clamp;
            importer.maxTextureSize = 4096;

            var settings = new TextureImporterSettings();
            importer.ReadTextureSettings(settings);
            settings.spriteMeshType = SpriteMeshType.FullRect;
            settings.spriteAlignment = (int)SpriteAlignment.Custom;
            settings.spritePivot = DefaultPivot(rel);
            settings.spriteGenerateFallbackPhysicsShape = false;

            // use the pivot and border from the json if there is one
            if (TryGetMeta(rel, out var e))
            {
                if (e.pivot != null && e.pivot.Length == 2)
                    settings.spritePivot = new Vector2(e.pivot[0], e.pivot[1]);
                if (e.border != null && e.border.Length == 4)
                    settings.spriteBorder = new Vector4(e.border[0], e.border[1], e.border[2], e.border[3]);
            }
            importer.SetTextureSettings(settings);
        }

        // default pivot based on the folder
        static Vector2 DefaultPivot(string rel)
        {
            if (rel.StartsWith("Character/")) return CharacterPivot;
            if (rel.StartsWith("Props/")) return new Vector2(0.5f, 0.08f);
            return new Vector2(0.5f, 0.5f);
        }

        // looks up a sprite in the json files
        static bool TryGetMeta(string rel, out Entry entry)
        {
            if (s_meta == null) LoadMeta();
            return s_meta.TryGetValue(rel, out entry);
        }

        // reads every sprite meta json file in the art folder
        static void LoadMeta()
        {
            s_meta = new Dictionary<string, Entry>();
            if (!Directory.Exists(ArtRoot)) return;
            foreach (var file in Directory.GetFiles(ArtRoot, "sprite_meta*.json"))
            {
                // json utility cant read dictionaries so we split it up by hand
                foreach (var kv in MiniJson.ParseObjectOfObjects(File.ReadAllText(file)))
                    s_meta[kv.Key] = JsonUtility.FromJson<Entry>(kv.Value);
            }
        }

        // clears the cache so the json gets read again next import
        public static void ResetCache() => s_meta = null;
    }

    // tiny json helper that splits the top object into each key and its raw json value
    static class MiniJson
    {
        public static IEnumerable<KeyValuePair<string, string>> ParseObjectOfObjects(string json)
        {
            int i = json.IndexOf('{') + 1;
            while (i > 0 && i < json.Length)
            {
                // find the next key in quotes
                int k0 = json.IndexOf('"', i);
                if (k0 < 0) yield break;
                int k1 = json.IndexOf('"', k0 + 1);
                string key = json.Substring(k0 + 1, k1 - k0 - 1);

                // find the matching closing brace for its value
                int v0 = json.IndexOf('{', k1);
                int depth = 0, v1 = v0;
                for (; v1 < json.Length; v1++)
                {
                    if (json[v1] == '{') depth++;
                    else if (json[v1] == '}' && --depth == 0) break;
                }
                yield return new KeyValuePair<string, string>(key, json.Substring(v0, v1 - v0 + 1));
                i = v1 + 1;
            }
        }
    }
}
