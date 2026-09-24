using UnityEngine;

namespace EmbrAIon.Reference.Unity
{
    public sealed class CounterSampleView : MonoBehaviour
    {
        [SerializeField] private CounterController counter;

        private const float PanelWidth = 360f;
        private const float PanelHeight = 240f;

        private void Awake()
        {
            if (counter == null)
            {
                counter = GetComponent<CounterController>();
            }

            EnsureCamera();
        }

        private void OnGUI()
        {
            if (counter == null)
            {
                return;
            }

            var panel = new Rect(
                (Screen.width - PanelWidth) * 0.5f,
                (Screen.height - PanelHeight) * 0.5f,
                PanelWidth,
                PanelHeight
            );

            var titleStyle = new GUIStyle(GUI.skin.label)
            {
                alignment = TextAnchor.MiddleCenter,
                fontSize = 20,
                fontStyle = FontStyle.Bold
            };

            var valueStyle = new GUIStyle(GUI.skin.label)
            {
                alignment = TextAnchor.MiddleCenter,
                fontSize = 28,
                fontStyle = FontStyle.Bold
            };

            GUILayout.BeginArea(panel, GUI.skin.window);
            GUILayout.Space(12f);
            GUILayout.Label("EmbrAIon Unity Reference", titleStyle);
            GUILayout.Space(18f);
            GUILayout.Label($"Value: {counter.Value}", valueStyle);
            GUILayout.FlexibleSpace();

            if (GUILayout.Button("Increment", GUILayout.Height(44f)))
            {
                counter.Increment();
            }

            if (GUILayout.Button("Reset", GUILayout.Height(44f)))
            {
                counter.ResetCounter();
            }

            GUILayout.Space(10f);
            GUILayout.EndArea();
        }

        private static void EnsureCamera()
        {
            if (Camera.main != null)
            {
                return;
            }

            var cameraObject = new GameObject("Main Camera");
            cameraObject.tag = "MainCamera";

            var camera = cameraObject.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(0.055f, 0.055f, 0.065f, 1f);
        }
    }
}
