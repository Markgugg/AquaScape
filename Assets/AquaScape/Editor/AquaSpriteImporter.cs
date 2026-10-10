using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace AquaScape.EditorTools
{
    /// <summary>
    /// Applies consistent import settings to every generated AquaScape sprite:
    /// 128 pixels per unit (one tile = one world unit), smooth filtering, no
    /// compression and per-folder pivots. Pivots / 9-slice borders that differ
    /// from the defaults come from the sprite_meta*.json files that the art
    /// scripts in Tools/ArtGen write next to the art.
    /// </summary>
    public class AquaSpriteImporter : AssetPostprocessor
    {
        const string ArtRoot = "Assets/AquaScape/Art/";
        public const float PixelsPerUnit = 128f;

        // The character frames are 192x224 with the feet 17px above the bottom.
        static readonly Vector2 CharacterPivot = new Vector2(0.5f, 17f / 224f);

        [System.Serializable] class Entry { public float[] pivot; public float[] border; }

        static Dictionary<string, Entry> s_meta;

        void OnPreprocessTexture()
        {
            if (!assetPath.StartsWith(ArtRoot)) return;
            var importer = (TextureImporter)assetImporter;
            string rel = assetPath.Substring(ArtRoot.Length);

            importer.textureType = TextureImporterType.Sprite;
            importer.spriteImportMode = SpriteImportMode.Single;
            importer.spritePixelsPerUnit = PixelsPerUnit;
            importer.filterMode = FilterMode.Bilinear;
            importer.textureCompression = TextureImporterCompression.Uncompressed;
            importer.alphaIsTransparency = true;
            importer.mipmapEnabled = rel.StartsWith("FX/cloud") || rel.StartsWith("Props/");
            importer.wrapMode = TextureWrapMode.Clamp;
            importer.maxTextureSize = 4096;

            var settings = new TextureImporterSettings();
            importer.ReadTextureSettings(settings);
            settings.spriteMeshType = SpriteMeshType.FullRect;
            settings.spriteAlignment = (int)SpriteAlignment.Custom;
            settings.spritePivot = DefaultPivot(rel);
            settings.spriteGenerateFallbackPhysicsShape = false;

            if (TryGetMeta(rel, out var e))
            {
                if (e.pivot != null && e.pivot.Length == 2)
                    settings.spritePivot = new Vector2(e.pivot[0], e.pivot[1]);
                if (e.border != null && e.border.Length == 4)
                    settings.spriteBorder = new Vector4(e.border[0], e.border[1], e.border[2], e.border[3]);
            }
            importer.SetTextureSettings(settings);
        }

        static Vector2 DefaultPivot(string rel)
        {
            if (rel.StartsWith("Character/")) return CharacterPivot;
            if (rel.StartsWith("Props/")) return new Vector2(0.5f, 0.08f);
            return new Vector2(0.5f, 0.5f);
        }

        /// <summary>Looks up an entry in any Art/sprite_meta*.json manifest.</summary>
        static bool TryGetMeta(string rel, out Entry entry)
        {
            if (s_meta == null) LoadMeta();
            return s_meta.TryGetValue(rel, out entry);
        }

        static void LoadMeta()
        {
            s_meta = new Dictionary<string, Entry>();
            if (!Directory.Exists(ArtRoot)) return;
            foreach (var file in Directory.GetFiles(ArtRoot, "sprite_meta*.json"))
            {
                // JsonUtility cannot read dictionaries, so parse the flat
                // { "path": { ... }, ... } layout with a tiny hand-written reader.
                foreach (var kv in MiniJson.ParseObjectOfObjects(File.ReadAllText(file)))
                    s_meta[kv.Key] = JsonUtility.FromJson<Entry>(kv.Value);
            }
        }

        /// <summary>Re-read manifests on the next import (called by the builder).</summary>
        public static void ResetCache() => s_meta = null;
    }

    /// <summary>Minimal JSON helper: splits a top-level object into key -> raw JSON value.</summary>
    static class MiniJson
    {
        public static IEnumerable<KeyValuePair<string, string>> ParseObjectOfObjects(string json)
        {
            int i = json.IndexOf('{') + 1;
            while (i > 0 && i < json.Length)
            {
                int k0 = json.IndexOf('"', i);
                if (k0 < 0) yield break;
                int k1 = json.IndexOf('"', k0 + 1);
                string key = json.Substring(k0 + 1, k1 - k0 - 1);
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
