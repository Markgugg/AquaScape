// AquaScape water surface (URP 2D Renderer).
//
// Drawn on one large sprite underneath the islands. Everything is computed in
// world space so it lines up with the tilemaps:
//   * colour palette blends Lagoon -> Glass City -> Moonpool by world x
//   * a blurred land mask (built by TerrainPainter) gives turquoise shallows
//     and animated foam rings around every shoreline
//   * animated caustics, sun glints, drifting cloud shadows (day)
//   * twinkling star reflections and bioluminescent specks (night)
Shader "AquaScape/Water"
{
    Properties
    {
        [PerRendererData] _MainTex ("Sprite", 2D) = "white" {}
        _MaskTex ("Land Mask", 2D) = "black" {}
        _MaskRect ("Mask Rect (x, y, w, h)", Vector) = (0, 0, 1, 1)

        _DeepLagoon ("Deep - Lagoon", Color) = (0.0, 0.64, 0.82, 1)
        _ShallowLagoon ("Shallow - Lagoon", Color) = (0.42, 0.96, 0.93, 1)
        _DeepCity ("Deep - City", Color) = (0.02, 0.56, 0.9, 1)
        _ShallowCity ("Shallow - City", Color) = (0.45, 0.9, 1.0, 1)
        _DeepNight ("Deep - Night", Color) = (0.05, 0.06, 0.26, 1)
        _ShallowNight ("Shallow - Night", Color) = (0.16, 0.3, 0.62, 1)

        _CausticStrength ("Caustic Strength", Float) = 0.32
        _GlintStrength ("Sun Glint Strength", Float) = 0.9
        _FoamStrength ("Foam Strength", Float) = 0.85
    }

    SubShader
    {
        Tags { "Queue" = "Transparent" "RenderType" = "Transparent" "RenderPipeline" = "UniversalPipeline" }
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        Cull Off

        Pass
        {
            Tags { "LightMode" = "Universal2D" }

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            struct Attributes
            {
                float4 positionOS : POSITION;
                float4 color : COLOR;
                float2 uv : TEXCOORD0;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float4 color : COLOR;
                float3 positionWS : TEXCOORD0;
            };

            TEXTURE2D(_MaskTex);
            SAMPLER(sampler_MaskTex);

            CBUFFER_START(UnityPerMaterial)
                float4 _MaskRect;
                half4 _DeepLagoon, _ShallowLagoon, _DeepCity, _ShallowCity, _DeepNight, _ShallowNight;
                float _CausticStrength, _GlintStrength, _FoamStrength;
            CBUFFER_END

            // set every frame by ZoneDirector
            float4 _AquaZoneEdges;

            // ---------------------------------------------------------------
            // noise helpers
            // ---------------------------------------------------------------
            float hash21(float2 p)
            {
                p = frac(p * float2(123.34, 456.21));
                p += dot(p, p + 45.32);
                return frac(p.x * p.y);
            }

            float2 hash22(float2 p)
            {
                float n = hash21(p);
                return float2(n, hash21(p + n));
            }

            float valueNoise(float2 p)
            {
                float2 i = floor(p);
                float2 f = frac(p);
                f = f * f * (3.0 - 2.0 * f);
                float a = hash21(i);
                float b = hash21(i + float2(1, 0));
                float c = hash21(i + float2(0, 1));
                float d = hash21(i + float2(1, 1));
                return lerp(lerp(a, b, f.x), lerp(c, d, f.x), f.y);
            }

            float fbm(float2 p)
            {
                float v = 0.0, a = 0.5;
                for (int i = 0; i < 4; i++)
                {
                    v += a * valueNoise(p);
                    p = p * 2.03 + 17.1;
                    a *= 0.5;
                }
                return v;
            }

            // classic iterated-trig water caustic pattern (expects p wrapped to
            // one 2*PI tile and offset far from the origin, as in the original)
            float caustic(float2 q, float time)
            {
                const float TAU = 6.28318530718;
                float2 p = frac(q / TAU) * TAU - 250.0;
                float2 i = p;
                float c = 1.0;
                const float inten = 0.005;
                for (int n = 0; n < 4; n++)
                {
                    float t = time * (1.0 - (3.5 / float(n + 1)));
                    i = p + float2(cos(t - i.x) + sin(t + i.y), sin(t - i.y) + cos(t + i.x));
                    c += 1.0 / length(float2(p.x / (sin(i.x + t) / inten), p.y / (cos(i.y + t) / inten)));
                }
                c /= 4.0;
                c = 1.17 - pow(abs(c), 1.4);
                return saturate(pow(abs(c), 8.0));
            }

            Varyings vert(Attributes v)
            {
                Varyings o;
                o.positionWS = TransformObjectToWorld(v.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.color = v.color;
                return o;
            }

            half4 frag(Varyings i) : SV_Target
            {
                float2 wp = i.positionWS.xy;
                float t = _Time.y;

                // land proximity (1 = land, 0 = open water)
                float2 muv = (wp - _MaskRect.xy) / _MaskRect.zw;
                float m = SAMPLE_TEXTURE2D(_MaskTex, sampler_MaskTex, muv).r;

                // zone blend by world x
                float z1 = smoothstep(_AquaZoneEdges.x, _AquaZoneEdges.y, wp.x);
                float z2 = smoothstep(_AquaZoneEdges.z, _AquaZoneEdges.w, wp.x);
                float3 deep = lerp(lerp(_DeepLagoon.rgb, _DeepCity.rgb, z1), _DeepNight.rgb, z2);
                float3 shallow = lerp(lerp(_ShallowLagoon.rgb, _ShallowCity.rgb, z1), _ShallowNight.rgb, z2);

                // base colour: deep -> shallow near land, with soft depth patches
                float n = fbm(wp * 0.18 + float2(t * 0.012, t * 0.008));
                float shore = smoothstep(0.0, 0.55, m);
                float3 col = lerp(deep, shallow, saturate(shore * 1.15 + (n - 0.5) * 0.35));

                // soft travelling swell bands
                float swell = sin(dot(wp, float2(0.55, 0.35)) * 1.7 + t * 0.9 + n * 5.0) * 0.5 + 0.5;
                col += (swell - 0.5) * 0.05 * (1.0 - z2);

                // caustics (stronger in shallow water)
                float c = caustic(wp * 0.35, t * 0.4);
                col += c * _CausticStrength * (0.35 + shore * 0.9) * lerp(float3(0.85, 1.0, 1.0), float3(0.45, 0.6, 1.0), z2) * lerp(1.0, 0.45, z2);

                // sun glints (day only)
                // tiny twinkling sparkles riding the swell
                float2 gc = floor(wp * 4.0);
                float gh = hash21(gc + 3.1);
                float2 gf = frac(wp * 4.0) - 0.5 - (hash22(gc + 1.7) - 0.5) * 0.6;
                float gtw = saturate(sin(t * (2.0 + gh * 3.0) + gh * 50.0));
                float g = smoothstep(0.09, 0.0, length(gf * float2(1.0, 1.8))) * step(0.82, gh) * gtw * gtw;
                col += g * _GlintStrength * (1.0 - z2) * (0.4 + 0.6 * (1.0 - shore));

                // shoreline foam: a solid lip plus rings that drift outward
                float rings = sin(m * 30.0 - t * 2.0 + n * 4.0) * 0.5 + 0.5;
                float ringZone = smoothstep(0.08, 0.28, m) * (1.0 - smoothstep(0.45, 0.55, m));
                float foam = smoothstep(0.8, 0.97, rings) * ringZone * 0.55 + smoothstep(0.42, 0.5, m);
                float3 foamCol = lerp(float3(1.0, 1.0, 1.0), float3(0.55, 0.75, 1.0), z2);
                col = lerp(col, foamCol, saturate(foam) * _FoamStrength);

                // drifting cloud shadows (day only)
                float cs = fbm(wp * 0.05 + float2(t * 0.025, t * 0.012));
                col *= 1.0 - smoothstep(0.52, 0.72, cs) * 0.16 * (1.0 - z2);

                // night: star reflections + bioluminescent specks
                float2 sc = floor(wp * 2.5);
                float sh = hash21(sc);
                float2 sf = frac(wp * 2.5) - 0.5 - (hash22(sc) - 0.5) * 0.7;
                float tw = 0.55 + 0.45 * sin(t * (1.5 + sh * 3.0) + sh * 60.0);
                float star = smoothstep(0.07, 0.0, length(sf)) * step(0.9, sh) * tw;
                float2 bc = floor(wp * 1.3 + float2(t * 0.05, 0));
                float bh = hash21(bc + 7.0);
                float2 bf = frac(wp * 1.3 + float2(t * 0.05, 0)) - 0.5 - (hash22(bc) - 0.5) * 0.6;
                float bio = smoothstep(0.12, 0.0, length(bf)) * step(0.88, bh) * (0.5 + 0.5 * sin(t * 1.3 + bh * 30.0));
                col += z2 * (star * float3(0.85, 0.9, 1.0) * 1.2 + bio * float3(0.3, 0.95, 1.0) * 0.6);

                // guard against NaNs reaching bloom
                if (any(isnan(col)) || any(isinf(col))) col = deep;
                return half4(saturate(col), 1.0) * i.color;
            }
            ENDHLSL
        }
    }
}
