'use client';

import React, { useMemo, useState, useEffect, useCallback } from 'react';
import { 
  Search, 
  Settings, 
  ChevronRight, 
  Layout, 
  Database,
  Download,
  Filter,
  Plus,
  ArrowLeft,
  Trash2,
  Edit,
  Save,
  X,
  MoreVertical,
  CheckCircle2,
  Table as TableIcon,
  Layers,
  Maximize2,
  Minimize2
} from 'lucide-react';
import { EntityDefinition } from '@/lib/api';

interface FioriPreviewProps {
  entities: EntityDefinition[];
  mainEntityName?: string;
  projectName: string;
}

type ViewMode = 'list' | 'detail' | 'create' | 'edit';

export function FioriPreview({ entities, mainEntityName, projectName }: FioriPreviewProps) {
  // Navigation State
  const [activeEntityName, setActiveEntityName] = useState<string>(mainEntityName || (entities.length > 0 ? entities[0].name : ''));
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [selectedItem, setSelectedItem] = useState<any>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  
  // Data State
  const [entityDataMap, setEntityDataMap] = useState<Record<string, any[]>>({});
  const [searchQuery, setSearchQuery] = useState('');

  // Escape key listener for full-screen
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape' && isFullscreen) {
      setIsFullscreen(false);
    }
  }, [isFullscreen]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Prevent body scroll when full-screen
  useEffect(() => {
    if (isFullscreen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [isFullscreen]);

  // Get active entity object
  const activeEntity = useMemo(() => {
    return entities.find(e => e.name === activeEntityName) || entities[0];
  }, [entities, activeEntityName]);

  // Initial Mock Data Generation
  useEffect(() => {
    if (entities.length > 0 && Object.keys(entityDataMap).length === 0) {
      const initialMap: Record<string, any[]> = {};
      entities.forEach(entity => {
        initialMap[entity.name] = generateMockData(entity);
      });
      setEntityDataMap(initialMap);
    }
  }, [entities]);

  // Sync active entity if mainEntityName changes
  useEffect(() => {
    if (mainEntityName) setActiveEntityName(mainEntityName);
  }, [mainEntityName]);

  function generateMockData(entity: EntityDefinition) {
    return Array.from({ length: 5 }).map((_, i) => {
      const row: Record<string, any> = {};
      entity.fields.forEach(field => {
        const type = (field.type || 'String').toLowerCase();
        const name = (field.name || '').toLowerCase();

        if (field.name === 'ID' || field.key) {
          if (type === 'uuid') {
            row[field.name] = `550e8400-e29b-41d4-a716-${446655440000 + i}`;
          } else {
            row[field.name] = `${entity.name.substring(0, 3).toUpperCase()}-${Math.random().toString(36).substr(2, 6).toUpperCase()}`;
          }
        } else if (type === 'string' || type === 'largestring') {
          if (name.includes('status') || name.includes('category')) {
            const options = ['Draft', 'In Progress', 'Completed', 'Approved', 'Rejected'];
            row[field.name] = options[i % options.length];
          } else {
            row[field.name] = `Sample ${field.name} ${i + 1}`;
          }
        } else if (type === 'integer' || type.startsWith('int')) {
          row[field.name] = (i + 1) * 100;
        } else if (type === 'boolean') {
          row[field.name] = i % 2 === 0;
        } else if (type === 'date') {
          row[field.name] = new Date(2024, 0, 15 + i).toISOString().split('T')[0];
        } else if (type === 'datetime' || type === 'timestamp' || type === 'managed') {
          row[field.name] = new Date(2024, 0, 15 + i, 10, 30).toISOString().replace('T', ' ').substring(0, 19);
        } else {
          row[field.name] = `Value ${i + 1}`;
        }
      });
      return row;
    });
  }

  // CRUD Handlers
  const handleDelete = (id: string) => {
    const newData = entityDataMap[activeEntityName].filter(item => {
      const keyField = activeEntity.fields.find(f => f.key)?.name || 'ID';
      return item[keyField] !== id;
    });
    setEntityDataMap({ ...entityDataMap, [activeEntityName]: newData });
    if (viewMode === 'detail') setViewMode('list');
  };

  const handleSave = (item: any) => {
    const keyField = activeEntity.fields.find(f => f.key)?.name || 'ID';
    const existingIndex = entityDataMap[activeEntityName].findIndex(i => i[keyField] === item[keyField]);
    
    let newData = [...entityDataMap[activeEntityName]];
    if (existingIndex >= 0) {
      newData[existingIndex] = item;
    } else {
      newData.unshift(item);
    }
    
    setEntityDataMap({ ...entityDataMap, [activeEntityName]: newData });
    setViewMode('list');
    setSelectedItem(null);
  };

  // Filtered Data
  const filteredData = useMemo(() => {
    const data = entityDataMap[activeEntityName] || [];
    if (!searchQuery) return data;
    return data.filter(item => 
      Object.values(item).some(val => 
        String(val).toLowerCase().includes(searchQuery.toLowerCase())
      )
    );
  }, [entityDataMap, activeEntityName, searchQuery]);

  if (!activeEntity) {
    return (
      <div className="flex flex-col items-center justify-center h-[500px] p-12 text-slate-500 bg-white/5 rounded-xl border border-dashed border-white/10">
        <Layout className="w-12 h-12 mb-4 opacity-20" />
        <p className="text-sm">Wait for Data Modeling to complete for a live preview...</p>
      </div>
    );
  }

  return (
    <div className={`${
      isFullscreen
        ? 'fixed inset-0 z-[999] w-screen h-screen'
        : 'w-full h-[650px] rounded-xl border border-slate-200 shadow-2xl'
    } overflow-hidden bg-white flex transition-all duration-300`}>
      {/* Sidebar Navigation */}
      <div className="w-56 bg-[#354a5f] flex flex-col shrink-0 border-r border-slate-300 transition-all duration-300">
        <div className="p-4 flex items-center gap-3 text-white border-b border-white/10">
          <Layers className="w-5 h-5 text-blue-400" />
          <span className="font-bold text-sm tracking-tighter">APP PREVIEW</span>
        </div>
        <div className="flex-1 overflow-auto p-2 space-y-1">
          <div className="px-3 py-2 text-[10px] font-bold text-white/40 uppercase tracking-widest">Entities</div>
          {entities.map(e => (
            <button
              key={e.name}
              onClick={() => {
                setActiveEntityName(e.name);
                setViewMode('list');
              }}
              className={`w-full text-left px-3 py-2 rounded text-xs transition-colors flex items-center gap-2 ${
                activeEntityName === e.name 
                ? 'bg-[#0854a0] text-white shadow-inner font-bold' 
                : 'text-white/60 hover:bg-white/5 hover:text-white'
              }`}
            >
              <Database className={`w-3 h-3 ${activeEntityName === e.name ? 'text-blue-300' : 'opacity-40'}`} />
              {e.name}
            </button>
          ))}
        </div>
        <div className="p-4 border-t border-white/10 text-[10px] text-white/40 italic">
          v2.0 Interactive Simulation
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col bg-[#f7f7f7] relative">
        {/* Fiori Top Header Shell */}
        <div className="bg-[#354a5f] p-3 flex items-center justify-between text-white shrink-0 border-l border-white/10">
          <div className="flex items-center gap-3">
            <span className="font-semibold text-xs opacity-80">{projectName}</span>
            <span className="text-white/20">/</span>
            <span className="text-xs font-bold text-blue-300 underline underline-offset-4">{activeEntityName}</span>
          </div>
          <div className="flex items-center gap-3">
             <button
               onClick={() => setIsFullscreen(!isFullscreen)}
               className="p-1.5 rounded hover:bg-white/10 transition-colors"
               title={isFullscreen ? 'Exit Full Screen (Esc)' : 'Full Screen'}
             >
               {isFullscreen ? (
                 <Minimize2 className="w-4 h-4 cursor-pointer opacity-70 hover:opacity-100" />
               ) : (
                 <Maximize2 className="w-4 h-4 cursor-pointer opacity-70 hover:opacity-100" />
               )}
             </button>
             <Settings className="w-4 h-4 cursor-pointer opacity-60 hover:opacity-100" />
          </div>
        </div>

        {/* Content Views */}
        <div className="flex-1 overflow-auto p-4 flex flex-col gap-4">
          {viewMode === 'list' ? (
            <>
              {/* List Report Header */}
              <div className="bg-white rounded p-6 shadow-sm border-b-2 border-[#346187] flex flex-col gap-6 shrink-0">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[#666] mb-1">List Report</div>
                    <h2 className="text-xl font-bold text-[#32363a]">{activeEntityName}s</h2>
                  </div>
                  <div className="flex gap-2">
                    <button 
                      onClick={() => {
                        setSelectedItem({});
                        setViewMode('create');
                      }}
                      className="bg-[#0854a0] text-white px-4 py-1.5 rounded text-sm font-medium hover:bg-[#074582] transition-colors flex items-center gap-2"
                    >
                      <Plus className="w-4 h-4" /> Create
                    </button>
                  </div>
                </div>

                {/* Filter Bar / Search */}
                <div className="bg-[#f2f2f2] p-4 rounded border border-slate-200">
                   <div className="flex items-center gap-4">
                      <div className="flex-1 flex flex-col gap-1.5">
                        <label className="text-[10px] font-bold text-[#666] uppercase">Search</label>
                        <div className="h-9 bg-white border border-[#bfbfbf] rounded px-3 flex items-center justify-between focus-within:border-[#0854a0] focus-within:ring-1 focus-within:ring-[#0854a0]/20 transition-all">
                          <input 
                            type="text" 
                            placeholder="Filter data..." 
                            className="bg-transparent border-none text-xs w-full focus:outline-none placeholder:text-slate-400"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                          />
                          <Search className="w-4 h-4 text-[#0854a0]" />
                        </div>
                      </div>
                      <div className="flex items-end h-full pt-6">
                        <button className="bg-[#0854a0] text-white px-6 py-2 text-xs font-bold rounded hover:bg-[#074582] shadow-sm">Go</button>
                      </div>
                   </div>
                </div>
              </div>

              {/* Table Content */}
              <div className="bg-white rounded shadow-sm border border-slate-200 flex flex-col flex-1 overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                  <span className="text-xs font-bold text-[#32363a]">Items ({filteredData.length})</span>
                  <div className="flex gap-3">
                    <Download className="w-4 h-4 text-[#0854a0] cursor-pointer hover:opacity-70" />
                    <Settings className="w-4 h-4 text-[#0854a0] cursor-pointer hover:opacity-70" />
                  </div>
                </div>
                <div className="overflow-auto flex-1">
                  <table className="w-full text-left border-collapse">
                    <thead className="bg-slate-50 sticky top-0 z-10 shadow-sm">
                      <tr className="border-b border-slate-200">
                        {activeEntity.fields.slice(0, 5).map(field => (
                          <th key={field.name} className="px-4 py-3 text-[#32363a] font-bold text-[10px] uppercase tracking-wider">
                            {field.name}
                          </th>
                        ))}
                        <th className="w-12"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {filteredData.length > 0 ? filteredData.map((row, idx) => (
                        <tr 
                          key={idx} 
                          onClick={() => {
                            setSelectedItem(row);
                            setViewMode('detail');
                          }}
                          className="hover:bg-[#f5faff] group cursor-pointer transition-all duration-150"
                        >
                          {activeEntity.fields.slice(0, 5).map(field => (
                            <td key={field.name} className="px-4 py-4 text-xs text-[#32363a]">
                              {typeof row[field.name] === 'boolean' ? (
                                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold ${row[field.name] ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                                  {row[field.name] ? <CheckCircle2 className="w-2.5 h-2.5" /> : null}
                                  {row[field.name] ? 'Active' : 'Inactive'}
                                </span>
                              ) : (
                                <span className="truncate block max-w-[150px]">{row[field.name]}</span>
                              )}
                            </td>
                          ))}
                          <td className="px-4 py-4 text-right">
                            <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-[#0854a0] transition-colors" />
                          </td>
                        </tr>
                      )) : (
                        <tr>
                          <td colSpan={10} className="py-20 text-center text-slate-400 text-xs italic">
                            No matching records found.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : viewMode === 'detail' ? (
            /* Object Page (Detail View) */
            <div className="flex flex-col gap-4 animate-in fade-in slide-in-from-right-4 duration-300">
              <div className="bg-white rounded p-6 shadow-sm border-b-2 border-[#346187] shrink-0">
                <button 
                  onClick={() => setViewMode('list')}
                  className="flex items-center gap-1 text-[#0854a0] text-xs font-bold mb-4 hover:underline"
                >
                  <ArrowLeft className="w-3 h-3" /> Back to List
                </button>
                <div className="flex justify-between items-start">
                  <div className="flex items-center gap-4">
                    <div className="w-16 h-16 rounded bg-[#f2f2f2] flex items-center justify-center text-[#346187]">
                      <Database className="w-8 h-8 opacity-40" />
                    </div>
                    <div>
                      <div className="text-[10px] uppercase font-bold text-[#666] mb-1">{activeEntityName} Details</div>
                      <h2 className="text-2xl font-bold text-[#32363a]">
                        {selectedItem[activeEntity.fields.find(f => !f.key && f.type?.toLowerCase() === 'string')?.name || activeEntity.fields[0].name]}
                      </h2>
                      <div className="flex gap-2 mt-2">
                        <span className="text-[10px] font-bold px-2 py-0.5 bg-blue-100 text-blue-700 rounded-sm italic uppercase">{selectedItem[activeEntity.fields.find(f => f.key)?.name || 'ID']}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button 
                      onClick={() => setViewMode('edit')}
                      className="bg-white border border-[#0854a0] text-[#0854a0] px-4 py-1.5 rounded text-sm font-medium hover:bg-blue-50 transition-colors flex items-center gap-2"
                    >
                      <Edit className="w-4 h-4" /> Edit
                    </button>
                    <button 
                      onClick={() => handleDelete(selectedItem[activeEntity.fields.find(f => f.key)?.name || 'ID'])}
                      className="bg-white border border-red-500 text-red-600 px-4 py-1.5 rounded text-sm font-medium hover:bg-red-50 transition-colors flex items-center gap-2"
                    >
                      <Trash2 className="w-4 h-4" /> Delete
                    </button>
                  </div>
                </div>
              </div>

              {/* Object Page Sections */}
              <div className="flex flex-col gap-4">
                <div className="bg-white rounded shadow-sm p-6 border border-slate-200">
                  <div className="flex items-center gap-2 mb-6 border-b border-slate-100 pb-3">
                    <Database className="w-4 h-4 text-[#346187]" />
                    <h3 className="text-sm font-bold text-[#32363a]">General Information</h3>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-y-8 gap-x-12">
                    {activeEntity.fields.map(field => (
                      <div key={field.name} className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-[#666] uppercase tracking-tighter opacity-70">{field.name}</label>
                        <div className="text-sm text-[#32363a] font-medium border-b border-slate-50 pb-1">
                          {typeof selectedItem[field.name] === 'boolean' 
                            ? (selectedItem[field.name] ? 'Yes' : 'No') 
                            : String(selectedItem[field.name] || '—')}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            /* Create/Edit Form View */
            <div className="flex flex-col gap-4 animate-in zoom-in-95 duration-200">
              <div className="bg-white rounded p-6 shadow-sm border-b-2 border-[#346187] shrink-0">
                <h2 className="text-xl font-bold text-[#32363a]">{viewMode === 'create' ? 'Create New' : 'Edit'} {activeEntityName}</h2>
                <p className="text-xs text-slate-500 mt-1">Enter the details for this record below.</p>
              </div>

              <div className="bg-white rounded shadow-sm p-6 border border-slate-200 flex-1">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                  {activeEntity.fields.map(field => (
                    <div key={field.name} className="flex flex-col gap-1.5">
                      <label className="text-[11px] font-bold text-[#666]">{field.name}{!field.nullable && <span className="text-red-500 ml-1">*</span>}</label>
                      {field.type?.toLowerCase() === 'boolean' ? (
                        <div className="flex items-center gap-4 py-2">
                           <label className="flex items-center gap-2 text-xs">
                             <input 
                                type="radio" 
                                checked={selectedItem[field.name] === true} 
                                onChange={() => setSelectedItem({...selectedItem, [field.name]: true})}
                             /> True
                           </label>
                           <label className="flex items-center gap-2 text-xs">
                             <input 
                                type="radio" 
                                checked={selectedItem[field.name] === false} 
                                onChange={() => setSelectedItem({...selectedItem, [field.name]: false})}
                             /> False
                           </label>
                        </div>
                      ) : (
                        <input 
                          type={(field.type?.toLowerCase() === 'date' || field.type?.toLowerCase() === 'datetime') ? 'date' : 'text'}
                          className="h-9 bg-white border border-[#bfbfbf] rounded px-3 text-xs focus:ring-1 focus:ring-[#0854a0] focus:border-[#0854a0] outline-none"
                          value={selectedItem[field.name] || ''}
                          disabled={field.key && viewMode === 'edit'}
                          onChange={(e) => setSelectedItem({...selectedItem, [field.name]: e.target.value})}
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Form Footer */}
              <div className="bg-white border-t border-slate-200 p-3 flex justify-end gap-3 rounded-b-xl shrink-0">
                <button 
                  onClick={() => setViewMode(viewMode === 'create' ? 'list' : 'detail')}
                  className="text-slate-600 border border-slate-300 px-6 py-1.5 rounded text-xs font-bold hover:bg-slate-50 transition-colors"
                >
                  Cancel
                </button>
                <button 
                  onClick={() => handleSave(selectedItem)}
                  className="bg-[#0854a0] text-white px-8 py-1.5 rounded text-xs font-bold hover:bg-[#074582] shadow-md transition-all flex items-center gap-2"
                >
                  <Save className="w-3.5 h-3.5" /> Save
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Floating Instructions Tooltip (Optional/Mock) */}
        {viewMode === 'list' && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-[#32363a]/90 text-white text-[10px] px-4 py-2 rounded-full shadow-lg backdrop-blur flex items-center gap-2 animate-bounce pointer-events-none">
            <CheckCircle2 className="w-3 h-3 text-green-400" />
            Click any row to test the Detail Page (Object Page)
          </div>
        )}
      </div>
    </div>
  );
}
