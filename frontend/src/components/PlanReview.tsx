'use client';

import { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Database,
  Link2,
  Zap,
  Plus,
  Trash2,
  Edit3,
  Check,
  X,
  Clock,
  FileCode,
  MessageSquare,
} from 'lucide-react';
import {
  ImplementationPlan,
  EntityDefinition,
  FieldDefinition,
  RelationshipDefinition,
  BusinessRule,
} from '@/lib/api';

interface PlanReviewProps {
  plan: ImplementationPlan;
  onUpdate: (updates: Partial<ImplementationPlan>) => void;
  onApprove: () => void;
  onRegenerate: () => void;
  isLoading?: boolean;
}

// CDS Type options
const CDS_TYPES = [
  'String',
  'LargeString',
  'Integer',
  'Decimal',
  'Boolean',
  'Date',
  'DateTime',
  'UUID',
  'Binary',
];

export default function PlanReview({
  plan,
  onUpdate,
  onApprove,
  onRegenerate,
  isLoading = false,
}: PlanReviewProps) {
  const [expandedEntities, setExpandedEntities] = useState<Set<string>>(
    new Set(plan.entities.map((e) => e.name))
  );
  const [editingField, setEditingField] = useState<{
    entityName: string;
    fieldIndex: number;
  } | null>(null);
  const [comments, setComments] = useState(plan.user_comments || '');
  const [showAddEntity, setShowAddEntity] = useState(false);
  const [newEntityName, setNewEntityName] = useState('');

  const toggleEntity = (name: string) => {
    const newExpanded = new Set(expandedEntities);
    if (newExpanded.has(name)) {
      newExpanded.delete(name);
    } else {
      newExpanded.add(name);
    }
    setExpandedEntities(newExpanded);
  };

  const handleFieldChange = (
    entityName: string,
    fieldIndex: number,
    field: keyof FieldDefinition,
    value: any
  ) => {
    const newEntities = plan.entities.map((entity) => {
      if (entity.name === entityName) {
        const newFields = [...entity.fields];
        newFields[fieldIndex] = { ...newFields[fieldIndex], [field]: value };
        return { ...entity, fields: newFields };
      }
      return entity;
    });
    onUpdate({ entities: newEntities });
  };

  const handleAddField = (entityName: string) => {
    const newEntities = plan.entities.map((entity) => {
      if (entity.name === entityName) {
        return {
          ...entity,
          fields: [
            ...entity.fields,
            {
              name: 'newField',
              type: 'String',
              length: 100,
              key: false,
              nullable: true,
            },
          ],
        };
      }
      return entity;
    });
    onUpdate({ entities: newEntities });
  };

  const handleRemoveField = (entityName: string, fieldIndex: number) => {
    const newEntities = plan.entities.map((entity) => {
      if (entity.name === entityName) {
        const newFields = entity.fields.filter((_, i) => i !== fieldIndex);
        return { ...entity, fields: newFields };
      }
      return entity;
    });
    onUpdate({ entities: newEntities });
  };

  const handleAddEntity = () => {
    if (!newEntityName.trim()) return;
    const newEntity: EntityDefinition = {
      name: newEntityName.trim(),
      description: `${newEntityName.trim()} entity`,
      fields: [
        { name: 'ID', type: 'UUID', key: true, nullable: false },
        { name: 'name', type: 'String', length: 100, key: false, nullable: false },
        { name: 'description', type: 'LargeString', key: false, nullable: true },
      ],
      aspects: ['cuid', 'managed'],
    };
    onUpdate({ entities: [...plan.entities, newEntity] });
    setNewEntityName('');
    setShowAddEntity(false);
    setExpandedEntities(new Set([...Array.from(expandedEntities), newEntity.name]));
  };

  const handleRemoveEntity = (entityName: string) => {
    const newEntities = plan.entities.filter((e) => e.name !== entityName);
    const newRelationships = plan.relationships.filter(
      (r) => r.source_entity !== entityName && r.target_entity !== entityName
    );
    onUpdate({ entities: newEntities, relationships: newRelationships });
  };

  const handleCommentsChange = (value: string) => {
    setComments(value);
    onUpdate({ user_comments: value } as any);
  };

  return (
    <div className="space-y-6">
      {/* Header with estimates */}
      <div className="flex items-center justify-between p-4 bg-gradient-to-r from-blue-500/10 to-purple-500/10 rounded-xl border border-blue-500/20">
        <div>
          <h2 className="text-lg font-semibold text-white">Implementation Plan</h2>
          <p className="text-sm text-gray-400">Review and modify before generation</p>
        </div>
        <div className="flex items-center gap-6">
          <div className="text-center">
            <div className="flex items-center gap-1 text-blue-400">
              <FileCode className="w-4 h-4" />
              <span className="text-xl font-bold">{plan.estimated_files}</span>
            </div>
            <p className="text-xs text-gray-500">Files</p>
          </div>
          <div className="text-center">
            <div className="flex items-center gap-1 text-purple-400">
              <Clock className="w-4 h-4" />
              <span className="text-xl font-bold">~{plan.estimated_time_seconds}s</span>
            </div>
            <p className="text-xs text-gray-500">Est. Time</p>
          </div>
        </div>
      </div>

      {/* Entities Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2">
            <Database className="w-4 h-4 text-blue-400" />
            Entities ({plan.entities.length})
          </h3>
          <button
            onClick={() => setShowAddEntity(true)}
            className="flex items-center gap-1 px-3 py-1.5 text-xs bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30 transition-colors"
          >
            <Plus className="w-3 h-3" />
            Add Entity
          </button>
        </div>

        {/* Add Entity Form */}
        {showAddEntity && (
          <div className="flex gap-2 p-3 bg-white/5 rounded-xl border border-white/10">
            <input
              type="text"
              value={newEntityName}
              onChange={(e) => setNewEntityName(e.target.value)}
              placeholder="EntityName (PascalCase)"
              className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 text-sm focus:outline-none focus:border-blue-500"
              onKeyPress={(e) => e.key === 'Enter' && handleAddEntity()}
            />
            <button
              onClick={handleAddEntity}
              className="p-2 bg-green-500/20 text-green-400 rounded-lg hover:bg-green-500/30"
            >
              <Check className="w-4 h-4" />
            </button>
            <button
              onClick={() => setShowAddEntity(false)}
              className="p-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Entity Cards */}
        {plan.entities.map((entity) => (
          <div
            key={entity.name}
            className="bg-white/5 rounded-xl border border-white/10 overflow-hidden"
          >
            {/* Entity Header */}
            <div
              className="flex items-center justify-between p-4 cursor-pointer hover:bg-white/5"
              onClick={() => toggleEntity(entity.name)}
            >
              <div className="flex items-center gap-3">
                {expandedEntities.has(entity.name) ? (
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-gray-400" />
                )}
                <div>
                  <span className="font-medium text-white">{entity.name}</span>
                  <span className="ml-2 text-xs text-gray-500">
                    {entity.fields.length} fields
                  </span>
                </div>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleRemoveEntity(entity.name);
                }}
                className="p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>

            {/* Entity Fields */}
            {expandedEntities.has(entity.name) && (
              <div className="px-4 pb-4 space-y-2">
                <div className="text-xs text-gray-500 mb-2">{entity.description}</div>
                
                {entity.fields.map((field, index) => (
                  <div
                    key={`${entity.name}-${index}`}
                    className="flex items-center gap-2 p-2 bg-gray-800/50 rounded-lg"
                  >
                    <span className="w-32 text-sm text-white truncate">{field.name}</span>
                    <select
                      value={field.type}
                      onChange={(e) =>
                        handleFieldChange(entity.name, index, 'type', e.target.value)
                      }
                      className="px-2 py-1 bg-gray-900 border border-gray-700 rounded text-xs text-white"
                    >
                      {CDS_TYPES.map((type) => (
                        <option key={type} value={type}>
                          {type}
                        </option>
                      ))}
                    </select>
                    {field.type === 'String' && (
                      <input
                        type="number"
                        value={field.length || 100}
                        onChange={(e) =>
                          handleFieldChange(entity.name, index, 'length', parseInt(e.target.value))
                        }
                        className="w-16 px-2 py-1 bg-gray-900 border border-gray-700 rounded text-xs text-white"
                        placeholder="Length"
                      />
                    )}
                    <label className="flex items-center gap-1 text-xs text-gray-400">
                      <input
                        type="checkbox"
                        checked={field.key}
                        onChange={(e) =>
                          handleFieldChange(entity.name, index, 'key', e.target.checked)
                        }
                        className="rounded"
                      />
                      Key
                    </label>
                    <label className="flex items-center gap-1 text-xs text-gray-400">
                      <input
                        type="checkbox"
                        checked={field.nullable}
                        onChange={(e) =>
                          handleFieldChange(entity.name, index, 'nullable', e.target.checked)
                        }
                        className="rounded"
                      />
                      Null
                    </label>
                    <button
                      onClick={() => handleRemoveField(entity.name, index)}
                      className="ml-auto p-1 text-gray-500 hover:text-red-400"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}

                <button
                  onClick={() => handleAddField(entity.name)}
                  className="flex items-center gap-1 px-3 py-1.5 text-xs text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                >
                  <Plus className="w-3 h-3" />
                  Add Field
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Relationships Section */}
      {plan.relationships.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2">
            <Link2 className="w-4 h-4 text-purple-400" />
            Relationships ({plan.relationships.length})
          </h3>
          <div className="grid gap-2">
            {plan.relationships.map((rel, index) => (
              <div
                key={index}
                className="flex items-center gap-3 p-3 bg-white/5 rounded-xl border border-white/10"
              >
                <span className="text-white">{rel.source_entity}</span>
                <span className="text-gray-500">→</span>
                <span className="text-white">{rel.target_entity}</span>
                <span className="text-xs text-gray-500 ml-auto">
                  {rel.type} ({rel.cardinality})
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Business Rules Section */}
      {plan.business_rules.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2">
            <Zap className="w-4 h-4 text-yellow-400" />
            Business Rules ({plan.business_rules.length})
          </h3>
          <div className="grid gap-2">
            {plan.business_rules.map((rule, index) => (
              <div
                key={index}
                className="p-3 bg-white/5 rounded-xl border border-white/10"
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium text-white">{rule.name}</span>
                  <span className="text-xs px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded">
                    {rule.rule_type}
                  </span>
                </div>
                <p className="text-sm text-gray-400 mt-1">{rule.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Comments Section */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-green-400" />
          Comments (Optional)
        </h3>
        <textarea
          value={comments}
          onChange={(e) => handleCommentsChange(e.target.value)}
          placeholder="Add any additional requirements or notes for the generation..."
          rows={3}
          className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors resize-none text-sm"
        />
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-between pt-4 border-t border-white/10">
        <button
          onClick={onRegenerate}
          disabled={isLoading}
          className="px-4 py-2 text-sm text-gray-400 hover:text-white hover:bg-white/5 rounded-xl transition-colors disabled:opacity-50"
        >
          Regenerate Plan
        </button>
        <button
          onClick={onApprove}
          disabled={isLoading || plan.entities.length === 0}
          className="px-6 py-2.5 bg-gradient-to-r from-green-600 to-green-500 rounded-xl font-medium text-white hover:from-green-500 hover:to-green-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? 'Processing...' : 'Approve & Continue'}
        </button>
      </div>
    </div>
  );
}
