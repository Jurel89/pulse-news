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
  const menuRef = useRef<HTMLDivElement>(null);
  const [menuPosition, setMenuPosition] = useState<{ top: number; left: number } | null>(null);
  const visibleActions = actions.filter((action) => !action.hidden);

  useEffect(() => {
    function updateMenuPosition() {
      if (!isOpen || !triggerRef.current) {
        return;
      }

      const rect = triggerRef.current.getBoundingClientRect();
      const spacing = 8;
      const estimatedItemHeight = 40;
      const estimatedMenuHeight = visibleActions.length * estimatedItemHeight + spacing * 2;
      const menuRect = menuRef.current?.getBoundingClientRect();
      const menuWidth = Math.max(menuRect?.width ?? 180, 180);
      const menuHeight = menuRect?.height ?? estimatedMenuHeight;
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      let left = align === "left"
        ? rect.left
        : rect.right - menuWidth;
      left = Math.min(Math.max(spacing, left), viewportWidth - menuWidth - spacing);

      const fitsBelow = rect.bottom + spacing + menuHeight <= viewportHeight - spacing;
      const fitsAbove = rect.top - spacing - menuHeight >= spacing;

      let top = rect.bottom + spacing;
      if (!fitsBelow && fitsAbove) {
        top = rect.top - menuHeight - spacing;
      } else if (!fitsBelow) {
        top = Math.max(spacing, viewportHeight - menuHeight - spacing);
      }

      setMenuPosition({
        top,
        left,
      });
    }

    updateMenuPosition();

    if (!isOpen) {
      return;
    }

    const frameId = window.requestAnimationFrame(updateMenuPosition);

    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);

    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [align, isOpen, visibleActions.length]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node;
      const clickedTrigger = dropdownRef.current?.contains(target) ?? false;
      const clickedMenu = menuRef.current?.contains(target) ?? false;

      if (!clickedTrigger && !clickedMenu) {
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
              ref={menuRef}
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
