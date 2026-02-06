'use client';

import { useState } from 'react';
import { ArrowLeft, ArrowRight, Check } from 'lucide-react';

interface WizardStep {
  id: number;
  name: string;
  shortName: string;
}

interface WizardLayoutProps {
  steps: WizardStep[];
  currentStep: number;
  onStepChange: (step: number) => void;
  onNext: () => void;
  onPrevious: () => void;
  canProceed: boolean;
  isGenerating: boolean;
  children: React.ReactNode;
}

export default function WizardLayout({
  steps,
  currentStep,
  onStepChange,
  onNext,
  onPrevious,
  canProceed,
  isGenerating,
  children,
}: WizardLayoutProps) {
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === steps.length - 1;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="glass border-b border-white/10 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <a href="/" className="text-xl font-bold text-white flex items-center gap-2">
            <span className="gradient-text">SAP</span> App Builder
          </a>
          
          {/* Step indicator */}
          <div className="hidden md:flex items-center gap-1">
            {steps.map((step, index) => (
              <button
                key={step.id}
                onClick={() => !isGenerating && index <= currentStep && onStepChange(index)}
                disabled={isGenerating || index > currentStep}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  index === currentStep
                    ? 'bg-blue-500 text-white'
                    : index < currentStep
                    ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
                    : 'text-gray-500 cursor-not-allowed'
                }`}
              >
                {index < currentStep ? (
                  <Check className="w-3 h-3 inline mr-1" />
                ) : null}
                {step.shortName}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* Progress bar */}
      <div className="h-1 bg-gray-800">
        <div
          className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 transition-all duration-300"
          style={{ width: `${((currentStep + 1) / steps.length) * 100}%` }}
        />
      </div>

      {/* Main content */}
      <main className="flex-1 max-w-5xl mx-auto w-full px-6 py-8">
        {/* Step title */}
        <div className="mb-8">
          <div className="text-sm text-blue-400 mb-1">
            Step {currentStep + 1} of {steps.length}
          </div>
          <h1 className="text-2xl font-bold text-white">
            {steps[currentStep].name}
          </h1>
        </div>

        {/* Step content */}
        <div className="glass rounded-2xl p-6 md:p-8 mb-8">
          {children}
        </div>
      </main>

      {/* Footer with navigation */}
      <footer className="glass border-t border-white/10 sticky bottom-0">
        <div className="max-w-5xl mx-auto px-6 py-4 flex justify-between items-center">
          <button
            onClick={onPrevious}
            disabled={isFirstStep || isGenerating}
            className={`px-6 py-2.5 rounded-xl font-medium flex items-center gap-2 transition-all ${
              isFirstStep || isGenerating
                ? 'text-gray-500 cursor-not-allowed'
                : 'text-white hover:bg-white/10'
            }`}
          >
            <ArrowLeft className="w-4 h-4" />
            Previous
          </button>

          <button
            onClick={onNext}
            disabled={!canProceed || isGenerating}
            className={`px-6 py-2.5 rounded-xl font-medium flex items-center gap-2 transition-all ${
              !canProceed || isGenerating
                ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                : 'bg-gradient-to-r from-blue-600 to-blue-500 text-white hover:from-blue-500 hover:to-blue-400 shadow-lg shadow-blue-500/25'
            }`}
          >
            {isLastStep ? (
              isGenerating ? 'Generating...' : 'Generate App'
            ) : (
              <>
                Next
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </footer>
    </div>
  );
}
