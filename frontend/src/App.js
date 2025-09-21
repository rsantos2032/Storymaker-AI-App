import React, { useState } from "react";
import "./App.css";

/**
 * StoryMaker Application
 *
 * A React frontend that allows users to generate AI-driven stories
 * by selecting a genre and number of scenes. The app communicates
 * with the backend API to generate story content and a downloadable video.
 *
 * Features:
 * - Input fields for genre and number of scenes
 * - Calls backend API to generate stories
 * - Displays story metadata and scenes
 * - Allows downloading the generated video
 */
function App() {
  /** API response object returned from backend */
  const [apiResponse, setApiResponse] = useState(null);

  /** Error message (if API request fails) */
  const [error, setError] = useState(null);

  /** User-selected story genre */
  const [genre, setGenre] = useState("fantasy");

  /** Number of scenes to generate */
  const [numScenes, setNumScenes] = useState(2);

  /** Whether API request is currently loading */
  const [loading, setLoading] = useState(false);

  /**
   * Handles story generation request.
   *
   * Sends POST request to backend with genre and number of scenes.
   * Updates state with API response or error message.
   */
  const handleGenerateStory = async () => {
    try {
      setError(null);
      setApiResponse(null);
      setLoading(true);

      const response = await fetch("http://localhost:8000/generate_story/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ genre, num_scenes: numScenes }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setApiResponse(data);
    } catch (err) {
      setError("Error connecting to API: " + err.message);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Handles downloading the generated video file.
   *
   * Uses the `metadata.video_file` path from API response
   * to trigger file download via backend endpoint.
   */
  const handleDownload = () => {
    if (apiResponse && apiResponse.metadata && apiResponse.metadata.video_file) {
      const filePath = encodeURIComponent(apiResponse.metadata.video_file);
      window.open(
        `http://localhost:8000/download_file/?path=${filePath}`,
        "_blank"
      );
    } else {
      alert("No file available for download.");
    }
  };

  return (
    <div className="container">
      <h1 className="title">StoryMaker</h1>

      {/* Genre Input */}
      <div className="inputGroup">
        <label className="label">Genre:</label>
        <input
          type="text"
          value={genre}
          onChange={(e) => setGenre(e.target.value)}
          className="input"
          disabled={loading}
        />
      </div>

      {/* Number of Scenes Input */}
      <div className="inputGroup">
        <label className="label">Number of Scenes:</label>
        <input
          type="number"
          value={numScenes}
          min="1"
          onChange={(e) => setNumScenes(parseInt(e.target.value) || 1)}
          className="input"
          disabled={loading}
        />
      </div>

      {/* Generate Button */}
      <button
        className={`button ${loading ? "buttonDisabled" : "buttonActive"}`}
        onClick={handleGenerateStory}
        disabled={loading}
      >
        {loading ? <span className="spinner"></span> : "Generate Story"}
      </button>

      {/* API Response / Error Display */}
      {(error || apiResponse) && (
        <div className="responseBox">
          {error && <p className="error">{error}</p>}

          {apiResponse && (
            <>
              <h2 className="storyTitle">{apiResponse.metadata.title}</h2>
              <p className="storyMeta">
                <strong>Genre:</strong> {apiResponse.metadata.genre}
              </p>
              <p className="storyIdea">{apiResponse.metadata.story_idea}</p>

              {/* Scenes List */}
              <h3>Scenes</h3>
              <div className="scenesContainer">
                {apiResponse.metadata.scenes.map((scene) => (
                  <div key={scene.scene} className="sceneCard">
                    <h4>Scene {scene.scene}</h4>
                    <p className="sceneSummary">
                      <em>{scene.summary}</em>
                    </p>
                    <p>{scene.description}</p>
                  </div>
                ))}
              </div>

              {/* Download Button */}
              <button className="downloadButton" onClick={handleDownload}>
                Download Video
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
