import { useState, useRef, useEffect } from "react";

export type DropdownOption = {
  value: string;
  label: string;
  disabled?: boolean;
};

type DropdownProps = {
  label: string;
  value: string;
  options: DropdownOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  helpText?: string;
};

export function Dropdown({
  label,
  value,
  options,
  onChange,
  placeholder = "Select an option",
  disabled = false,
  helpText
}: DropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const selectedOption = options.find(opt => opt.value === value);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <label className="dropdown-label">
      <span>{label}</span>
      <div className="dropdown-wrapper" ref={dropdownRef}>
        <button
          type="button"
          className={`dropdown-trigger ${disabled ? "disabled" : ""}`}
          onClick={() => !disabled && setIsOpen(!isOpen)}
          disabled={disabled}
        >
          <span className={selectedOption ? "dropdown-value" : "dropdown-placeholder"}>
            {selectedOption?.label ?? placeholder}
          </span>
          <svg className={`dropdown-arrow ${isOpen ? "open" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
        {isOpen && (
          <div className="dropdown-menu">
            {options.map(option => (
              <button
                key={option.value}
                type="button"
                className={`dropdown-option ${option.value === value ? "selected" : ""} ${option.disabled ? "disabled" : ""}`}
                onClick={() => {
                  if (!option.disabled) {
                    onChange(option.value);
                    setIsOpen(false);
                  }
                }}
                disabled={option.disabled}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}
      </div>
      {helpText ? <HelpText text={helpText} /> : null}
    </label>
  );
}

type HelpTextProps = {
  text: string;
};

export function HelpText({ text }: HelpTextProps) {
  const [showTooltip, setShowTooltip] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);

  return (
    <span className="help-text-wrapper">
      <span
        className="help-text-icon"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onClick={() => setShowTooltip(!showTooltip)}
        role="button"
        tabIndex={0}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      </span>
      {showTooltip ? (
        <div ref={tooltipRef} className="help-text-tooltip">
          {text}
        </div>
      ) : null}
    </span>
  );
}

type FormSectionProps = {
  title: string;
  description?: string;
  children: React.ReactNode;
};

export function FormSection({ title, description, children }: FormSectionProps) {
  return (
    <div className="form-section">
      <div className="form-section-header">
        <h3 className="form-section-title">{title}</h3>
        {description ? <p className="form-section-description">{description}</p> : null}
      </div>
      <div className="form-section-content">
        {children}
      </div>
    </div>
  );
}
