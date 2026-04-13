import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export type ActionItem = {
  label: string;
  onClick: () => void;
  variant?: "default" | "danger" | "primary";
  disabled?: boolean;
  hidden?: boolean;
  icon?: React.ReactNode;
};

type ActionDropdownProps = {
  actions: ActionItem[];
  align?: "left" | "right";
};

export function ActionDropdown({ actions, align = "right" }: ActionDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [menuPosition, setMenuPosition] = useState<{ top: number; left: number } | null>(null);

  useEffect(() => {
    function updateMenuPosition() {
      if (!isOpen || !triggerRef.current) {
        return;
      }

      const rect = triggerRef.current.getBoundingClientRect();
      const menuWidth = 180;
      const spacing = 8;
      const left = align === "left"
        ? rect.left
        : Math.max(spacing, rect.right - menuWidth);

      setMenuPosition({
        top: rect.bottom + spacing,
        left,
      });
    }

    updateMenuPosition();

    if (!isOpen) {
      return;
    }

    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);

    return () => {
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [align, isOpen]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      return () => {
        document.removeEventListener("keydown", handleEscape);
      };
    }
  }, [isOpen]);

  const visibleActions = actions.filter((action) => !action.hidden);

  if (visibleActions.length === 0) {
    return null;
  }

  return (
    <div className="action-dropdown" ref={dropdownRef}>
      <button
        ref={triggerRef}
        className="action-dropdown-trigger"
        onClick={() => setIsOpen(!isOpen)}
        type="button"
        aria-haspopup="true"
        aria-expanded={isOpen}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <circle cx="8" cy="3" r="1.5" fill="currentColor" />
          <circle cx="8" cy="8" r="1.5" fill="currentColor" />
          <circle cx="8" cy="13" r="1.5" fill="currentColor" />
        </svg>
        <span className="sr-only">Actions</span>
      </button>

      {isOpen && menuPosition
        ? createPortal(
            <div
              className="action-dropdown-menu action-dropdown-menu-portal"
              role="menu"
              style={{ top: `${menuPosition.top}px`, left: `${menuPosition.left}px` }}
            >
              {visibleActions.map((action) => (
                <button
                  key={`${action.label}-${action.variant ?? "default"}`}
                  className={`action-dropdown-item ${action.variant || "default"}`}
                  onClick={() => {
                    action.onClick();
                    setIsOpen(false);
                  }}
                  disabled={action.disabled}
                  type="button"
                  role="menuitem"
                >
                  {action.icon && (
                    <span className="action-dropdown-item-icon">{action.icon}</span>
                  )}
                  <span className="action-dropdown-item-label">{action.label}</span>
                </button>
              ))}
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}
