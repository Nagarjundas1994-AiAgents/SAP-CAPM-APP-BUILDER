'use client';

import Link from 'next/link';
import { Sparkles, ArrowRight, Layers, Shield, Zap, Code2 } from 'lucide-react';

export default function HomePage() {
  return (
    <main className="min-h-screen">
      {/* Hero Section */}
      <section className="relative overflow-hidden">
        {/* Background effects */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-900/20 via-transparent to-transparent" />
        <div className="absolute top-20 left-1/4 w-72 h-72 bg-blue-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-20 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl" />

        <div className="relative max-w-7xl mx-auto px-6 py-24">
          {/* Badge */}
          <div className="flex justify-center mb-8">
            <div className="glass px-4 py-2 rounded-full flex items-center gap-2 text-sm text-blue-300">
              <Sparkles className="w-4 h-4" />
              AI-Powered SAP Development
            </div>
          </div>

          {/* Main heading */}
          <h1 className="text-5xl md:text-7xl font-bold text-center mb-6">
            <span className="text-white">Build SAP Apps</span>
            <br />
            <span className="gradient-text">10x Faster</span>
          </h1>

          <p className="text-xl text-gray-400 text-center max-w-2xl mx-auto mb-12">
            Generate production-ready SAP CAPM + Fiori applications using
            AI-powered multi-agent orchestration. From requirements to deployment in minutes.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/builder"
              className="group px-8 py-4 bg-gradient-to-r from-blue-600 to-blue-500 rounded-xl font-semibold text-white flex items-center justify-center gap-2 hover:from-blue-500 hover:to-blue-400 transition-all duration-300 shadow-lg shadow-blue-500/25"
            >
              Start Building
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Link>
            <a
              href="/api/docs"
              target="_blank"
              className="px-8 py-4 glass rounded-xl font-semibold text-white flex items-center justify-center gap-2 hover:bg-white/10 transition-all duration-300"
            >
              <Code2 className="w-5 h-5" />
              API Docs
            </a>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="max-w-7xl mx-auto px-6 py-20">
        <h2 className="text-3xl font-bold text-white text-center mb-12">
          Everything You Need to Build SAP Apps
        </h2>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[
            {
              icon: Layers,
              title: '9 AI Agents',
              description: 'Specialized agents for every aspect of SAP development',
              color: 'blue',
            },
            {
              icon: Zap,
              title: 'Multi-LLM',
              description: 'OpenAI, Gemini, DeepSeek, and more',
              color: 'yellow',
            },
            {
              icon: Shield,
              title: 'SAP Compliant',
              description: 'Following official SAP SDK best practices',
              color: 'green',
            },
            {
              icon: Code2,
              title: 'Full Stack',
              description: 'CDS, OData, Fiori Elements, MTA deployment',
              color: 'purple',
            },
          ].map((feature, i) => (
            <div
              key={i}
              className="glass p-6 rounded-2xl card-hover"
            >
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${
                feature.color === 'blue' ? 'bg-blue-500/20 text-blue-400' :
                feature.color === 'yellow' ? 'bg-yellow-500/20 text-yellow-400' :
                feature.color === 'green' ? 'bg-green-500/20 text-green-400' :
                'bg-purple-500/20 text-purple-400'
              }`}>
                <feature.icon className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">{feature.title}</h3>
              <p className="text-gray-400 text-sm">{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Agent Pipeline Preview */}
      <section className="max-w-7xl mx-auto px-6 py-20">
        <h2 className="text-3xl font-bold text-white text-center mb-4">
          AI Agent Pipeline
        </h2>
        <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
          Watch 9 specialized agents work together to generate your complete SAP application
        </p>

        <div className="glass-dark rounded-2xl p-8">
          <div className="flex flex-wrap justify-center gap-4">
            {[
              'Requirements',
              'Data Model',
              'Services',
              'Logic',
              'Fiori UI',
              'Security',
              'Extensions',
              'Deployment',
              'Validation',
            ].map((agent, i) => (
              <div
                key={i}
                className="flex items-center gap-3"
              >
                <div className={`w-3 h-3 rounded-full ${
                  i === 0 ? 'bg-green-500' : 'bg-gray-600'
                }`} />
                <span className="text-gray-300 text-sm">{agent}</span>
                {i < 8 && (
                  <ArrowRight className="w-4 h-4 text-gray-600" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/10 py-8">
        <div className="max-w-7xl mx-auto px-6 text-center text-gray-500 text-sm">
          Built with FastAPI + LangGraph + Next.js • SAP App Builder
        </div>
      </footer>
    </main>
  );
}
