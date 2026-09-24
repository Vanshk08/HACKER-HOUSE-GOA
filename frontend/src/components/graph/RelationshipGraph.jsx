import React, { useState, useRef, useMemo } from 'react';
import {
  ZoomIn,
  ZoomOut,
  RefreshCw,
  User,
  CreditCard,
  Receipt,
  MapPin,
  Smartphone,
  Mail,
  History,
  X,
  Database,
} from 'lucide-react';
import { Card } from '../common/Card';
import { Button } from '../common/Button';

export function RelationshipGraph({ graphData }) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [selectedNode, setSelectedNode] = useState(null);

  const containerRef = useRef(null);

  const nodes = useMemo(() => graphData?.nodes || [], [graphData?.nodes]);
  const edges = useMemo(() => graphData?.edges || [], [graphData?.edges]);

  // Compute clean layout coordinates for nodes
  const layoutNodes = useMemo(() => {
    if (nodes.length === 0) return [];

    // Find root transaction or case
    const caseNode = nodes.find((n) => n.type === 'case') || nodes[0];
    const txnNode = nodes.find((n) => n.type === 'transaction' && n.category === 'flagged');
    const custNode = nodes.find((n) => n.type === 'customer');
    const cardNodes = nodes.filter((n) => n.type === 'card');
    const regionNodes = nodes.filter((n) => n.type === 'region');
    const otherNodes = nodes.filter(
      (n) => !['case', 'customer'].includes(n.type) && !(n.type === 'transaction' && n.category === 'flagged') && !['card', 'region'].includes(n.type)
    );

    const positions = {};
    const centerX = 360;
    const centerY = 220;

    // Fixed radial/hierarchical positions for enterprise clarity
    if (caseNode) positions[caseNode.id] = { x: centerX - 180, y: centerY - 90 };
    if (custNode) positions[custNode.id] = { x: centerX - 180, y: centerY + 70 };
    if (txnNode) positions[txnNode.id] = { x: centerX, y: centerY };

    cardNodes.forEach((cn, idx) => {
      positions[cn.id] = { x: centerX - 70, y: centerY + 140 + idx * 60 };
    });

    regionNodes.forEach((rn, idx) => {
      positions[rn.id] = { x: centerX + 180, y: centerY - 80 + idx * 70 };
    });

    otherNodes.forEach((on, idx) => {
      positions[on.id] = {
        x: centerX + 190,
        y: centerY + 60 + idx * 65,
      };
    });

    return nodes.map((n) => ({
      ...n,
      x: positions[n.id]?.x ?? centerX,
      y: positions[n.id]?.y ?? centerY,
    }));
  }, [nodes]);

  const handleMouseDown = (e) => {
    // Only drag on canvas background, not on node clicks
    if (e.target.tagName === 'svg' || e.target.tagName === 'rect' || e.target.id === 'graph-canvas') {
      setIsDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }
  };

  const handleMouseUp = () => setIsDragging(false);

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setSelectedNode(null);
  };

  const getNodeIcon = (type) => {
    switch (type) {
      case 'customer':
        return User;
      case 'card':
        return CreditCard;
      case 'transaction':
        return Receipt;
      case 'region':
        return MapPin;
      case 'device':
        return Smartphone;
      case 'email':
        return Mail;
      case 'history':
        return History;
      default:
        return Database;
    }
  };

  const getNodeColor = (type, category) => {
    if (category === 'flagged') return { bg: '#fee2e2', border: '#ef4444', text: '#991b1b' };
    switch (type) {
      case 'case':
        return { bg: '#0f172a', border: '#334155', text: '#ffffff' };
      case 'customer':
        return { bg: '#e0e7ff', border: '#6366f1', text: '#3730a3' };
      case 'card':
        return { bg: '#f1f5f9', border: '#94a3b8', text: '#334155' };
      case 'region':
        return { bg: '#fef3c7', border: '#f59e0b', text: '#92400e' };
      case 'device':
        return { bg: '#fee2e2', border: '#f87171', text: '#b91c1c' };
      default:
        return { bg: '#f8fafc', border: '#cbd5e1', text: '#475569' };
    }
  };

  if (nodes.length === 0) {
    return (
      <Card title="Entity Relationship Graph" subtitle="TigerGraph Cloud HHGOA_IEEE Graph Structure">
        <div className="p-8 text-center text-slate-400 text-xs">
          No graph relationships available for this case.
        </div>
      </Card>
    );
  }

  return (
    <Card
      title="TigerGraph Relationship Visualization"
      subtitle="Interactive entity graph showing transaction, customer, card, and regional links"
      action={
        <div className="flex items-center gap-1.5">
          <Button size="sm" variant="outline" icon={ZoomIn} onClick={() => setZoom((z) => Math.min(z + 0.2, 2.5))}>
            Zoom In
          </Button>
          <Button size="sm" variant="outline" icon={ZoomOut} onClick={() => setZoom((z) => Math.max(z - 0.2, 0.5))}>
            Zoom Out
          </Button>
          <Button size="sm" variant="outline" icon={RefreshCw} onClick={resetView}>
            Reset
          </Button>
        </div>
      }
      className="overflow-hidden relative"
      bodyClassName="p-0!"
    >
      <div
        ref={containerRef}
        id="graph-canvas"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        className="w-full h-[450px] bg-slate-50/50 cursor-grab active:cursor-grabbing relative overflow-hidden select-none"
      >
        <svg
          className="w-full h-full"
          viewBox="0 0 760 450"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: 'center center',
            transition: isDragging ? 'none' : 'transform 0.15s ease-out',
          }}
        >
          {/* Subtle grid pattern */}
          <defs>
            <pattern id="graph-grid" width="20" height="20" patternUnits="userSpaceOnUse">
              <circle cx="10" cy="10" r="1" fill="#e2e8f0" />
            </pattern>
            <marker
              id="arrowhead"
              markerWidth="8"
              markerHeight="6"
              refX="18"
              refY="3"
              orient="auto"
            >
              <polygon points="0 0, 8 3, 0 6" fill="#94a3b8" />
            </marker>
          </defs>

          <rect width="100%" height="100%" fill="url(#graph-grid)" />

          {/* Edges */}
          <g>
            {edges.map((edge) => {
              const srcNode = layoutNodes.find((n) => n.id === edge.source);
              const tgtNode = layoutNodes.find((n) => n.id === edge.target);
              if (!srcNode || !tgtNode) return null;

              const midX = (srcNode.x + tgtNode.x) / 2;
              const midY = (srcNode.y + tgtNode.y) / 2;

              return (
                <g key={edge.id} className="opacity-90">
                  <line
                    x1={srcNode.x}
                    y1={srcNode.y}
                    x2={tgtNode.x}
                    y2={tgtNode.y}
                    stroke="#cbd5e1"
                    strokeWidth="1.8"
                    strokeDasharray={edge.type.includes('history') ? '4 2' : 'none'}
                    markerEnd="url(#arrowhead)"
                  />
                  {/* Edge label badge */}
                  <rect
                    x={midX - 32}
                    y={midY - 8}
                    width="64"
                    height="16"
                    rx="4"
                    fill="#ffffff"
                    stroke="#e2e8f0"
                    strokeWidth="1"
                  />
                  <text
                    x={midX}
                    y={midY + 3.5}
                    textAnchor="middle"
                    fill="#64748b"
                    fontSize="8"
                    fontWeight="600"
                    fontFamily="monospace"
                  >
                    {edge.label}
                  </text>
                </g>
              );
            })}
          </g>

          {/* Nodes */}
          <g>
            {layoutNodes.map((node) => {
              const isSelected = selectedNode?.id === node.id;
              const color = getNodeColor(node.type, node.category);

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x}, ${node.y})`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedNode(node);
                  }}
                  className="cursor-pointer group"
                >
                  {/* Node outer glow on selection */}
                  {isSelected && (
                    <circle
                      r="32"
                      fill="none"
                      stroke="#6366f1"
                      strokeWidth="3"
                      strokeDasharray="3 3"
                      className="animate-spin"
                    />
                  )}

                  {/* Node Body */}
                  <rect
                    x="-65"
                    y="-20"
                    width="130"
                    height="40"
                    rx="10"
                    fill={color.bg}
                    stroke={isSelected ? '#4f46e5' : color.border}
                    strokeWidth={isSelected ? '2.5' : '1.5'}
                    className="transition-all duration-150 shadow-xs"
                  />

                  {/* Node Label */}
                  <text
                    x="0"
                    y="1"
                    textAnchor="middle"
                    fill={color.text}
                    fontSize="11"
                    fontWeight="700"
                    fontFamily="sans-serif"
                  >
                    {node.label}
                  </text>

                  {/* Node Type Badge */}
                  <text
                    x="0"
                    y="12"
                    textAnchor="middle"
                    fill={node.type === 'case' ? '#94a3b8' : '#64748b'}
                    fontSize="7.5"
                    fontWeight="600"
                    textTransform="uppercase"
                  >
                    {node.type}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>

        {/* Selected Node Details Drawer */}
        {selectedNode && (
          <div className="absolute right-3 top-3 bottom-3 w-72 bg-white/95 backdrop-blur-xs border border-slate-200 rounded-xl shadow-lg p-4 z-20 overflow-y-auto">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100 mb-3">
              <div className="flex items-center gap-2">
                {(() => {
                  const NodeIcon = getNodeIcon(selectedNode.type);
                  return <NodeIcon className="h-4 w-4 text-slate-600 shrink-0" />;
                })()}
                <span className="text-xs font-bold text-slate-900">{selectedNode.label}</span>
                <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                  {selectedNode.type}
                </span>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-slate-400 hover:text-slate-700 cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-2 text-xs">
              <div className="text-[10px] uppercase font-bold text-slate-400">Ground Truth Attributes</div>
              {selectedNode.properties &&
                Object.entries(selectedNode.properties).map(([k, v]) => (
                  <div key={k} className="p-2 bg-slate-50 rounded border border-slate-100 flex flex-col">
                    <span className="text-[10px] text-slate-400 font-mono uppercase">{k}</span>
                    <strong className="text-slate-800 font-mono text-[11px] truncate">
                      {v !== null && v !== undefined ? String(v) : 'null'}
                    </strong>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
