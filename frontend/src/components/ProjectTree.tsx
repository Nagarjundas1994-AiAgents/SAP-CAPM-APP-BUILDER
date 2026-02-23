/**
 * ProjectTree Component
 *
 * Displays the generated project as a collapsible folder tree.
 * Clicking a file opens it in the ArtifactEditor.
 */

import React, { useState, useMemo } from "react";

interface GeneratedFile {
  path: string;
  content: string;
  file_type: string;
}

interface ProjectTreeProps {
  files: GeneratedFile[];
  onSelectFile?: (file: GeneratedFile) => void;
  selectedPath?: string;
}

interface TreeNode {
  name: string;
  fullPath: string;
  isDir: boolean;
  children: TreeNode[];
  file?: GeneratedFile;
}

function buildTree(files: GeneratedFile[]): TreeNode {
  const root: TreeNode = { name: "project", fullPath: "", isDir: true, children: [] };

  for (const file of files) {
    const parts = file.path.split("/");
    let current = root;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isLast = i === parts.length - 1;
      const fullPath = parts.slice(0, i + 1).join("/");

      let child = current.children.find((c) => c.name === part);
      if (!child) {
        child = {
          name: part,
          fullPath,
          isDir: !isLast,
          children: [],
          file: isLast ? file : undefined,
        };
        current.children.push(child);
      }
      current = child;
    }
  }

  // Sort: directories first, then alphabetically
  const sortTree = (node: TreeNode) => {
    node.children.sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    node.children.forEach(sortTree);
  };
  sortTree(root);

  return root;
}

const FILE_ICONS: Record<string, string> = {
  ".cds": "📐",
  ".js": "📜",
  ".ts": "📘",
  ".json": "📋",
  ".yaml": "⚙️",
  ".yml": "⚙️",
  ".html": "🌐",
  ".css": "🎨",
  ".md": "📝",
  ".csv": "📊",
  ".properties": "🏷️",
  ".xml": "📰",
};

function getFileIcon(name: string): string {
  const ext = "." + name.split(".").pop();
  return FILE_ICONS[ext] || "📄";
}

function TreeItem({
  node,
  depth,
  onSelect,
  selectedPath,
}: {
  node: TreeNode;
  depth: number;
  onSelect?: (file: GeneratedFile) => void;
  selectedPath?: string;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const isSelected = selectedPath === node.fullPath;

  if (node.isDir) {
    return (
      <div>
        <div
          style={{
            ...styles.item,
            paddingLeft: `${12 + depth * 16}px`,
            cursor: "pointer",
          }}
          onClick={() => setExpanded(!expanded)}
        >
          <span style={styles.dirArrow}>{expanded ? "▼" : "▶"}</span>
          <span style={styles.dirIcon}>📁</span>
          <span style={styles.dirName}>{node.name}</span>
          <span style={styles.childCount}>{node.children.length}</span>
        </div>
        {expanded && (
          <div>
            {node.children.map((child) => (
              <TreeItem
                key={child.fullPath}
                node={child}
                depth={depth + 1}
                onSelect={onSelect}
                selectedPath={selectedPath}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      style={{
        ...styles.item,
        ...styles.fileItem,
        paddingLeft: `${28 + depth * 16}px`,
        backgroundColor: isSelected ? "#1e3a5f" : "transparent",
        borderLeft: isSelected ? "2px solid #3b82f6" : "2px solid transparent",
      }}
      onClick={() => node.file && onSelect?.(node.file)}
    >
      <span style={styles.fileIcon}>{getFileIcon(node.name)}</span>
      <span style={styles.fileName}>{node.name}</span>
      {node.file && (
        <span style={styles.fileSize}>
          {node.file.content.length > 1024
            ? `${(node.file.content.length / 1024).toFixed(1)}KB`
            : `${node.file.content.length}B`}
        </span>
      )}
    </div>
  );
}

export default function ProjectTree({ files, onSelectFile, selectedPath }: ProjectTreeProps) {
  const tree = useMemo(() => buildTree(files), [files]);

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.headerIcon}>🗂️</span>
        <span style={styles.headerTitle}>Project Structure</span>
        <span style={styles.fileCountBadge}>{files.length} files</span>
      </div>
      <div style={styles.treeBody}>
        {tree.children.map((child) => (
          <TreeItem
            key={child.fullPath}
            node={child}
            depth={0}
            onSelect={onSelectFile}
            selectedPath={selectedPath}
          />
        ))}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: "#0f172a",
    borderRadius: "12px",
    border: "1px solid #1e293b",
    overflow: "hidden",
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
    fontSize: "13px",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "12px 16px",
    borderBottom: "1px solid #1e293b",
    background: "#1e293b",
  },
  headerIcon: { fontSize: "16px" },
  headerTitle: { fontWeight: 700, color: "#e2e8f0", flex: 1 },
  fileCountBadge: {
    fontSize: "11px",
    padding: "2px 8px",
    background: "#334155",
    borderRadius: "8px",
    color: "#94a3b8",
  },
  treeBody: { padding: "8px 0", maxHeight: "500px", overflowY: "auto" as const },
  item: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    padding: "4px 12px",
    color: "#cbd5e1",
    userSelect: "none" as const,
    transition: "background 0.15s",
  },
  fileItem: { cursor: "pointer" },
  dirArrow: { fontSize: "8px", color: "#64748b", width: "12px", textAlign: "center" as const },
  dirIcon: { fontSize: "14px" },
  dirName: { fontWeight: 600, color: "#e2e8f0" },
  childCount: { fontSize: "10px", color: "#64748b", marginLeft: "auto" },
  fileIcon: { fontSize: "14px" },
  fileName: { color: "#cbd5e1" },
  fileSize: { fontSize: "10px", color: "#64748b", marginLeft: "auto" },
};
