using System.Collections.Generic;
using UnityEngine;

namespace AquaScape
{
    /// <summary>Raises a bridge once every lantern in the group is lit.</summary>
    public class LanternGroup : MonoBehaviour
    {
        public List<MoonLantern> lanterns = new List<MoonLantern>();
        public BridgeBuilder bridge;

        public int LitCount
        {
            get
            {
                int n = 0;
                foreach (var l in lanterns) if (l.IsLit) n++;
                return n;
            }
        }

        public void OnLanternLit()
        {
            int lit = LitCount;
            if (lit < lanterns.Count)
            {
                UIManager.Hint($"Moon lanterns lit: {lit} / {lanterns.Count}", 2.5f);
                return;
            }
            UIManager.Toast("The moon path appears", "All lanterns are glowing");
            bridge?.Activate(0.8f);
        }
    }
}
