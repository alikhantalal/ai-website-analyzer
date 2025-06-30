import React, { useState, useEffect } from "react";
import "./App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [url, setUrl] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState("");
  const [result, setResult] = useState(null);
  const [recentAnalyses, setRecentAnalyses] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    // Load recent analyses on component mount
    loadRecentAnalyses();
  }, []);

  const loadRecentAnalyses = async () => {
    try {
      const response = await axios.get(`${API}/analyses`);
      setRecentAnalyses(response.data.slice(0, 5));
    } catch (error) {
      console.error("Failed to load recent analyses:", error);
    }
  };

  const downloadReport = async (sessionId) => {
    try {
      const response = await axios.get(`${API}/export/${sessionId}?format=pdf`, {
        responseType: 'blob'
      });
      
      // Create blob link to download
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `website_analysis_${sessionId.slice(0, 8)}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Failed to download report:", error);
      setError("Failed to download report. Please try again.");
    }
  };

  const validateUrl = (url) => {
    const urlPattern = /^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$/;
    return urlPattern.test(url);
  };

  const startAnalysis = async () => {
    if (!url.trim()) {
      setError("Please enter a website URL");
      return;
    }

    if (!validateUrl(url)) {
      setError("Please enter a valid website URL");
      return;
    }

    setError("");
    setIsAnalyzing(true);
    setProgress(0);
    setResult(null);
    setProgressMessage("Starting analysis...");

    try {
      // Start analysis
      const response = await axios.post(`${API}/analyze`, {
        url: url.trim(),
      });

      const sessionId = response.data.session_id;
      setCurrentSessionId(sessionId);

      // Poll for progress
      pollProgress(sessionId);
    } catch (error) {
      console.error("Analysis failed:", error);
      setError("Failed to start analysis. Please try again.");
      setIsAnalyzing(false);
    }
  };

  const pollProgress = async (sessionId) => {
    const pollInterval = setInterval(async () => {
      try {
        const progressResponse = await axios.get(`${API}/progress/${sessionId}`);
        const progressData = progressResponse.data;

        setProgress(progressData.progress);
        setProgressMessage(progressData.message);

        if (progressData.status === "completed") {
          clearInterval(pollInterval);
          // Get final result
          const resultResponse = await axios.get(`${API}/result/${sessionId}`);
          setResult(resultResponse.data);
          setIsAnalyzing(false);
          loadRecentAnalyses(); // Refresh recent analyses
        } else if (progressData.status === "error") {
          clearInterval(pollInterval);
          setError(progressData.message);
          setIsAnalyzing(false);
        }
      } catch (error) {
        console.error("Progress polling failed:", error);
        clearInterval(pollInterval);
        setError("Analysis failed. Please try again.");
        setIsAnalyzing(false);
      }
    }, 1000);

    // Timeout after 5 minutes
    setTimeout(() => {
      clearInterval(pollInterval);
      if (isAnalyzing) {
        setError("Analysis timeout. Please try again.");
        setIsAnalyzing(false);
      }
    }, 300000);
  };

  const getScoreColor = (score) => {
    if (score >= 80) return "text-green-500";
    if (score >= 60) return "text-yellow-500";
    return "text-red-500";
  };

  const getScoreBgColor = (score) => {
    if (score >= 80) return "bg-green-500";
    if (score >= 60) return "bg-yellow-500";
    return "bg-red-500";
  };

  const getPriorityColor = (priority) => {
    switch (priority.toLowerCase()) {
      case "high": return "bg-red-100 text-red-800";
      case "medium": return "bg-yellow-100 text-yellow-800";
      case "low": return "bg-green-100 text-green-800";
      default: return "bg-gray-100 text-gray-800";
    }
  };

  const CircularProgress = ({ score, label }) => {
    const circumference = 2 * Math.PI * 45;
    const strokeDasharray = circumference;
    const strokeDashoffset = circumference - (score / 100) * circumference;

    return (
      <div className="flex flex-col items-center">
        <div className="relative w-24 h-24">
          <svg className="w-24 h-24 transform -rotate-90" viewBox="0 0 100 100">
            <circle
              cx="50"
              cy="50"
              r="45"
              stroke="currentColor"
              strokeWidth="8"
              fill="transparent"
              className="text-gray-200"
            />
            <circle
              cx="50"
              cy="50"
              r="45"
              stroke="currentColor"
              strokeWidth="8"
              fill="transparent"
              strokeDasharray={strokeDasharray}
              strokeDashoffset={strokeDashoffset}
              className={getScoreColor(score)}
              strokeLinecap="round"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className={`text-2xl font-bold ${getScoreColor(score)}`}>
              {score}
            </span>
          </div>
        </div>
        <span className="mt-2 text-sm font-medium text-gray-600">{label}</span>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <div className="bg-blue-600 rounded-lg p-2 mr-3">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <h1 className="text-2xl font-bold text-gray-900">AI Website Analyzer</h1>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Hero Section */}
        {!result && (
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              Analyze Any Website with AI-Powered Insights
            </h2>
            <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
              Get comprehensive SEO, performance, and technical analysis with actionable AI recommendations in seconds.
            </p>

            {/* URL Input */}
            <div className="max-w-2xl mx-auto">
              <div className="flex gap-4 mb-4">
                <div className="flex-1">
                  <input
                    type="text"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="Enter website URL (e.g., example.com)"
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    disabled={isAnalyzing}
                    onKeyPress={(e) => e.key === 'Enter' && !isAnalyzing && startAnalysis()}
                  />
                </div>
                <button
                  onClick={startAnalysis}
                  disabled={isAnalyzing}
                  className="px-8 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isAnalyzing ? "Analyzing..." : "Analyze Website"}
                </button>
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                  <p className="text-red-800">{error}</p>
                </div>
              )}

              {/* Progress Indicator */}
              {isAnalyzing && (
                <div className="bg-white rounded-lg shadow-md p-6">
                  <div className="flex items-center mb-4">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600 mr-3"></div>
                    <span className="text-lg font-medium text-gray-900">Analyzing your website...</span>
                  </div>
                  
                  <div className="w-full bg-gray-200 rounded-full h-3 mb-4">
                    <div 
                      className="bg-blue-600 h-3 rounded-full transition-all duration-300 ease-out"
                      style={{ width: `${progress}%` }}
                    ></div>
                  </div>
                  
                  <p className="text-gray-600">{progressMessage}</p>
                  <p className="text-sm text-gray-500 mt-2">{progress}% complete</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Results Dashboard */}
        {result && (
          <div className="space-y-8">
            {/* Header with URL and New Analysis Button */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">Analysis Results</h2>
                  <p className="text-gray-600">{result.url}</p>
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={() => downloadReport(result.session_id)}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Export PDF
                  </button>
                  <button
                    onClick={() => {
                      setResult(null);
                      setUrl("");
                      setProgress(0);
                      setError("");
                    }}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    New Analysis
                  </button>
                </div>
              </div>

              {/* Overall Score */}
              <div className="text-center">
                <CircularProgress score={result.overall_score} label="Overall Score" />
              </div>
            </div>

            {/* Detailed Scores */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
              <div className="bg-white rounded-lg shadow-md p-6 text-center">
                <CircularProgress score={result.performance_score} label="Performance" />
                <div className="mt-4 space-y-1">
                  <p className="text-sm text-gray-600">
                    Response Time: {(result.analysis_data.performance.response_time || 0).toFixed(2)}s
                  </p>
                  <p className="text-sm text-gray-600">
                    Page Size: {Math.round((result.analysis_data.performance.content_size || 0) / 1024)}KB
                  </p>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow-md p-6 text-center">
                <CircularProgress score={result.seo_score} label="SEO" />
                <div className="mt-4 space-y-1">
                  <p className="text-sm text-gray-600">
                    Title: {result.analysis_data.seo.title_length} chars
                  </p>
                  <p className="text-sm text-gray-600">
                    Meta Desc: {result.analysis_data.seo.meta_description_length} chars
                  </p>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow-md p-6 text-center">
                <CircularProgress score={result.technical_score} label="Technical" />
                <div className="mt-4 space-y-1">
                  <p className="text-sm text-gray-600">
                    HTTPS: {result.analysis_data.technical.https_enabled ? "✓" : "✗"}
                  </p>
                  <p className="text-sm text-gray-600">
                    Viewport: {result.analysis_data.technical.has_viewport ? "✓" : "✗"}
                  </p>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow-md p-6 text-center">
                <CircularProgress score={result.accessibility_score} label="Accessibility" />
                <div className="mt-4 space-y-1">
                  <p className="text-sm text-gray-600">
                    Alt Text: {Math.round(result.analysis_data.accessibility.images_with_alt_percentage || 0)}%
                  </p>
                  <p className="text-sm text-gray-600">
                    Images: {result.analysis_data.performance.images_count}
                  </p>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow-md p-6 text-center">
                <CircularProgress score={result.schema_faq_score} label="Schema & FAQ" />
                <div className="mt-4 space-y-1">
                  <p className="text-sm text-gray-600">
                    Schema: {result.schema_faq_analysis.has_schema ? "✓" : "✗"}
                  </p>
                  <p className="text-sm text-gray-600">
                    FAQ: {result.schema_faq_analysis.has_faq ? "✓" : "✗"}
                  </p>
                </div>
              </div>
            </div>

            {/* Schema & FAQ Analysis Section */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-xl font-bold text-gray-900 mb-4">Schema & FAQ Analysis</h3>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Checkpoint Category */}
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h4 className="font-medium text-gray-900 mb-2">Checkpoint Category</h4>
                  <div className="text-lg font-semibold mb-2">
                    {result.schema_faq_analysis?.category_label || "❌ Neither Schema nor FAQ"}
                  </div>
                  <div className="text-sm text-gray-600">
                    Score: {result.schema_faq_score || 0}/100
                  </div>
                </div>

                {/* Quick Overview */}
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h4 className="font-medium text-gray-900 mb-2">Quick Overview</h4>
                  <div className="space-y-1 text-sm">
                    <p className="text-gray-600">
                      <span className="font-medium">Schema Markup:</span> {result.schema_faq_analysis?.has_schema ? "✓ Found" : "✗ Not Found"}
                    </p>
                    <p className="text-gray-600">
                      <span className="font-medium">FAQ Structure:</span> {result.schema_faq_analysis?.has_faq ? "✓ Found" : "✗ Not Found"}
                    </p>
                    {result.schema_faq_analysis?.schema_details?.schema_types && result.schema_faq_analysis.schema_details.schema_types.length > 0 && (
                      <p className="text-gray-600">
                        <span className="font-medium">Schema Types:</span> {result.schema_faq_analysis.schema_details.schema_types.length}
                      </p>
                    )}
                    {result.schema_faq_analysis?.faq_details?.question_count > 0 && (
                      <p className="text-gray-600">
                        <span className="font-medium">FAQ Questions:</span> {result.schema_faq_analysis.faq_details.question_count}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Detailed Analysis */}
              <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Schema Details */}
                {result.schema_faq_analysis?.has_schema && (
                  <div className="border border-gray-200 rounded-lg p-4">
                    <h4 className="font-medium text-gray-900 mb-3 flex items-center">
                      <span className="w-2 h-2 bg-green-500 rounded-full mr-2"></span>
                      Schema Markup Found
                    </h4>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-600">JSON-LD Scripts:</span>
                        <span className="font-medium">{result.schema_faq_analysis.schema_details.json_ld_count || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Microdata Elements:</span>
                        <span className="font-medium">{result.schema_faq_analysis.schema_details.microdata_count || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">RDFa Elements:</span>
                        <span className="font-medium">{result.schema_faq_analysis.schema_details.rdfa_count || 0}</span>
                      </div>
                      
                      {result.schema_faq_analysis.schema_details.schema_types && result.schema_faq_analysis.schema_details.schema_types.length > 0 && (
                        <div className="mt-3">
                          <span className="text-gray-600 font-medium">Schema Types Found:</span>
                          <div className="mt-1 space-y-1">
                            {result.schema_faq_analysis.schema_details.schema_types.slice(0, 5).map((type, index) => (
                              <div key={index} className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                                {type}
                              </div>
                            ))}
                            {result.schema_faq_analysis.schema_details.schema_types.length > 5 && (
                              <div className="text-xs text-gray-500">
                                +{result.schema_faq_analysis.schema_details.schema_types.length - 5} more types...
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* FAQ Details */}
                {result.schema_faq_analysis?.has_faq && (
                  <div className="border border-gray-200 rounded-lg p-4">
                    <h4 className="font-medium text-gray-900 mb-3 flex items-center">
                      <span className="w-2 h-2 bg-blue-500 rounded-full mr-2"></span>
                      FAQ Structure Found
                    </h4>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Questions Detected:</span>
                        <span className="font-medium">{result.schema_faq_analysis.faq_details.question_count || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Answers Detected:</span>
                        <span className="font-medium">{result.schema_faq_analysis.faq_details.answer_count || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">FAQ Containers:</span>
                        <span className="font-medium">{result.schema_faq_analysis.faq_details.faq_containers || 0}</span>
                      </div>
                      
                      {result.schema_faq_analysis.faq_details.faq_indicators && result.schema_faq_analysis.faq_details.faq_indicators.length > 0 && (
                        <div className="mt-3">
                          <span className="text-gray-600 font-medium">FAQ Indicators Found:</span>
                          <div className="mt-1 space-y-1">
                            {result.schema_faq_analysis.faq_details.faq_indicators.slice(0, 3).map((indicator, index) => (
                              <div key={index} className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">
                                {indicator}
                              </div>
                            ))}
                            {result.schema_faq_analysis.faq_details.faq_indicators.length > 3 && (
                              <div className="text-xs text-gray-500">
                                +{result.schema_faq_analysis.faq_details.faq_indicators.length - 3} more indicators...
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* When no schema or FAQ found */}
                {!result.schema_faq_analysis?.has_schema && !result.schema_faq_analysis?.has_faq && (
                  <div className="lg:col-span-2 border border-gray-200 rounded-lg p-4">
                    <h4 className="font-medium text-gray-900 mb-3 flex items-center">
                      <span className="w-2 h-2 bg-red-500 rounded-full mr-2"></span>
                      No Schema or FAQ Structure Detected
                    </h4>
                    <div className="text-sm text-gray-600">
                      <p className="mb-2">This website doesn't appear to have structured data markup or FAQ sections.</p>
                      <p className="text-xs">
                        <strong>Recommendations:</strong> Consider adding JSON-LD schema markup and organizing common questions into an FAQ section to improve SEO and user experience.
                      </p>
                    </div>
                  </div>
                )}

                {/* Only schema, no FAQ */}
                {result.schema_faq_analysis?.has_schema && !result.schema_faq_analysis?.has_faq && (
                  <div className="border border-gray-200 rounded-lg p-4">
                    <h4 className="font-medium text-gray-900 mb-3 flex items-center">
                      <span className="w-2 h-2 bg-orange-500 rounded-full mr-2"></span>
                      Missing FAQ Structure
                    </h4>
                    <div className="text-sm text-gray-600">
                      <p className="mb-2">Great schema markup found, but no FAQ section detected.</p>
                      <p className="text-xs">
                        <strong>Recommendation:</strong> Add an FAQ section with proper schema markup to improve user experience and search visibility.
                      </p>
                    </div>
                  </div>
                )}

                {/* Only FAQ, no schema */}
                {!result.schema_faq_analysis?.has_schema && result.schema_faq_analysis?.has_faq && (
                  <div className="border border-gray-200 rounded-lg p-4">
                    <h4 className="font-medium text-gray-900 mb-3 flex items-center">
                      <span className="w-2 h-2 bg-orange-500 rounded-full mr-2"></span>
                      Missing Schema Markup
                    </h4>
                    <div className="text-sm text-gray-600">
                      <p className="mb-2">FAQ structure found, but no structured data markup detected.</p>
                      <p className="text-xs">
                        <strong>Recommendation:</strong> Add JSON-LD schema markup to help search engines better understand your content structure.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* AI Insights */}
            {result.ai_insights && result.ai_insights.recommendations && (
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-xl font-bold text-gray-900 mb-4">AI-Powered Recommendations</h3>
                <div className="space-y-4">
                  {result.ai_insights.recommendations.map((rec, index) => (
                    <div key={index} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="text-lg font-medium text-gray-900">{rec.title}</h4>
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getPriorityColor(rec.priority)}`}>
                          {rec.priority} Priority
                        </span>
                      </div>
                      <p className="text-gray-600 mb-2">{rec.description}</p>
                      {rec.impact && (
                        <p className="text-sm text-blue-600">Expected Impact: {rec.impact}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Detailed Issues */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Performance Issues */}
              {result.analysis_data.performance.issues && result.analysis_data.performance.issues.length > 0 && (
                <div className="bg-white rounded-lg shadow-md p-6">
                  <h3 className="text-lg font-bold text-gray-900 mb-4">Performance Issues</h3>
                  <ul className="space-y-2">
                    {result.analysis_data.performance.issues.map((issue, index) => (
                      <li key={index} className="flex items-start">
                        <span className="text-red-500 mr-2">•</span>
                        <span className="text-gray-700">{issue}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* SEO Issues */}
              {result.analysis_data.seo.issues && result.analysis_data.seo.issues.length > 0 && (
                <div className="bg-white rounded-lg shadow-md p-6">
                  <h3 className="text-lg font-bold text-gray-900 mb-4">SEO Issues</h3>
                  <ul className="space-y-2">
                    {result.analysis_data.seo.issues.map((issue, index) => (
                      <li key={index} className="flex items-start">
                        <span className="text-yellow-500 mr-2">•</span>
                        <span className="text-gray-700">{issue}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Page Overview */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-lg font-bold text-gray-900 mb-4">Page Overview</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h4 className="font-medium text-gray-900 mb-2">Content</h4>
                  <p className="text-sm text-gray-600">Words: {result.analysis_data.parsed_content.word_count}</p>
                  <p className="text-sm text-gray-600">H1 Tags: {result.analysis_data.parsed_content.headings.h1.length}</p>
                  <p className="text-sm text-gray-600">Images: {result.analysis_data.parsed_content.images.length}</p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h4 className="font-medium text-gray-900 mb-2">Links</h4>
                  <p className="text-sm text-gray-600">Internal: {result.analysis_data.seo.internal_links}</p>
                  <p className="text-sm text-gray-600">External: {result.analysis_data.seo.external_links}</p>
                  <p className="text-sm text-gray-600">Total: {result.analysis_data.seo.internal_links + result.analysis_data.seo.external_links}</p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h4 className="font-medium text-gray-900 mb-2">Meta Data</h4>
                  <p className="text-sm text-gray-600">Title: {result.analysis_data.parsed_content.title ? 'Present' : 'Missing'}</p>
                  <p className="text-sm text-gray-600">Description: {result.analysis_data.parsed_content.meta_description ? 'Present' : 'Missing'}</p>
                  <p className="text-sm text-gray-600">Viewport: {result.analysis_data.technical.has_viewport ? 'Present' : 'Missing'}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Recent Analyses */}
        {!result && recentAnalyses.length > 0 && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Recent Analyses</h3>
            <div className="space-y-3">
              {recentAnalyses.map((analysis, index) => (
                <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <p className="font-medium text-gray-900">{analysis.url}</p>
                    <p className="text-sm text-gray-600">
                      {new Date(analysis.created_at).toLocaleDateString()} - Score: {analysis.overall_score}/100
                    </p>
                    {analysis.schema_faq_analysis?.category_label && (
                      <p className="text-xs text-gray-500 mt-1">
                        {analysis.schema_faq_analysis.category_label}
                      </p>
                    )}
                  </div>
                  <div className={`px-3 py-1 rounded-full text-sm font-medium ${getScoreBgColor(analysis.overall_score)} text-white`}>
                    {analysis.overall_score}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;