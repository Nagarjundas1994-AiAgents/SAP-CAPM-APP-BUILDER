'use client';

import { useState, useEffect } from 'react';
import {
  File,
  FolderOpen,
  Save,
  X,
  ChevronRight,
  ChevronDown,
  Database,
  Server,
  Palette,
  Rocket,
  FileCode,
  Search,
} from 'lucide-react';
import { Artifact, GenerationResult } from '@/lib/api';

interface ArtifactEditorProps {
  result: GenerationResult;
  onSave: (path: string, content: string) => Promise<void>;
  onClose: () => void;
}

export default function ArtifactEditor({
  result,
  onSave,
  onClose,
}: ArtifactEditorProps) {
  const [selectedFile, setSelectedFile] = useState<Artifact | null>(null);
  const [editedContent, setEditedContent] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(['db', 'srv', 'app', 'deployment', 'docs']));

  // All artifacts flattened
  const allArtifacts = [
    ...result.artifacts_db.map(a => ({ ...a, category: 'db' })),
    ...result.artifacts_srv.map(a => ({ ...a, category: 'srv' })),
    ...result.artifacts_app.map(a => ({ ...a, category: 'app' })),
    ...result.artifacts_deployment.map(a => ({ ...a, category: 'deployment' })),
    ...result.artifacts_docs.map(a => ({ ...a, category: 'docs' })),
  ];

  const filteredArtifacts = allArtifacts.filter(a => 
    a.path.toLowerCase().includes(searchQuery.toLowerCase())
  );

  useEffect(() => {
    if (selectedFile) {
      setEditedContent(selectedFile.content);
    }
  }, [selectedFile]);

  const handleSave = async () => {
    if (!selectedFile) return;
    setIsSaving(true);
    try {
      await onSave(selectedFile.path, editedContent);
      // Update local artifact content
      selectedFile.content = editedContent;
    } catch (error) {
      console.error('Failed to save artifact:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const getFileIcon = (category: string) => {
    switch (category) {
      case 'db': return <Database className="w-4 h-4 text-blue-400" />;
      case 'srv': return <Server className="w-4 h-4 text-green-400" />;
      case 'app': return <Palette className="w-4 h-4 text-purple-400" />;
      case 'deployment': return <Rocket className="w-4 h-4 text-orange-400" />;
      case 'docs': return <FileCode className="w-4 h-4 text-gray-400" />;
      default: return <File className="w-4 h-4 text-gray-400" />;
    }
  };

  const categories = [
    { id: 'db', name: 'Database (CDS)', artifacts: result.artifacts_db },
    { id: 'srv', name: 'Service Layer (JS/CDS)', artifacts: result.artifacts_srv },
    { id: 'app', name: 'Fiori Elements UI', artifacts: result.artifacts_app },
    { id: 'deployment', name: 'Deployment (YAML/JSON)', artifacts: result.artifacts_deployment },
    { id: 'docs', name: 'Documentation', artifacts: result.artifacts_docs },
  ];

  const toggleFolder = (id: string) => {
    const newExpanded = new Set(expandedFolders);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedFolders(newExpanded);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 md:p-8">
      <div className="bg-gray-900 border border-white/10 w-full h-full max-w-7xl rounded-2xl flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <FolderOpen className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h2 className="font-semibold text-white">Artifact Editor</h2>
              <p className="text-xs text-gray-400">Modify generated files before downloading the project</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* File Explorer */}
          <div className="w-80 border-r border-white/10 flex flex-col bg-white/5 overflow-hidden">
            <div className="p-4 border-b border-white/10">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <input
                  type="text"
                  placeholder="Search files..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 bg-black/20 border border-white/10 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-2">
              {categories.map((cat) => {
                if (cat.artifacts.length === 0) return null;
                const isExpanded = expandedFolders.has(cat.id);
                return (
                  <div key={cat.id} className="mb-2">
                    <button
                      onClick={() => toggleFolder(cat.id)}
                      className="w-full flex items-center gap-2 px-2 py-1.5 text-xs font-medium text-gray-400 uppercase tracking-wider hover:text-white transition-colors"
                    >
                      {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                      {cat.name}
                    </button>
                    {isExpanded && (
                      <div className="mt-1 space-y-0.5">
                        {cat.artifacts.map((file) => (
                          <button
                            key={file.path}
                            onClick={() => setSelectedFile(file)}
                            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-left transition-all ${
                              selectedFile?.path === file.path
                                ? 'bg-blue-500/20 text-white'
                                : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
                            }`}
                          >
                            {getFileIcon(cat.id)}
                            <span className="truncate">{file.path}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Editor Area */}
          <div className="flex-1 flex flex-col overflow-hidden bg-black/40">
            {selectedFile ? (
              <>
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm text-gray-300">{selectedFile.path}</span>
                    <span className="text-xs px-2 py-0.5 bg-white/5 rounded text-gray-500 uppercase">{selectedFile.file_type}</span>
                  </div>
                  <button
                    onClick={handleSave}
                    disabled={isSaving || editedContent === selectedFile.content}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-500 transition-all disabled:opacity-50 disabled:bg-blue-600/50"
                  >
                    {isSaving ? (
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    ) : (
                      <Save className="w-4 h-4" />
                    )}
                    {isSaving ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>
                <div className="flex-1 overflow-hidden relative">
                  <textarea
                    value={editedContent}
                    onChange={(e) => setEditedContent(e.target.value)}
                    className="w-full h-full p-6 bg-transparent text-gray-300 font-mono text-sm resize-none focus:outline-none leading-relaxed"
                    spellCheck={false}
                  />
                  {/* Subtle line numbers or grid can be added here */}
                </div>
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-gray-500">
                <div className="p-6 bg-white/5 rounded-full mb-4">
                  <File className="w-12 h-12 opacity-20" />
                </div>
                <p>Select a file from the sidebar to start editing</p>
                <p className="text-sm opacity-50">You can customize the generated code here</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
