"use client";

type MultiValueOption = {
  value: string;
  label: string;
  disabled?: boolean;
};

interface MultiValuePickerProps {
  placeholder: string;
  options: MultiValueOption[];
  values: string[];
  onChange: (values: string[]) => void;
  className?: string;
}

export function MultiValuePicker({
  placeholder,
  options,
  values,
  onChange,
  className,
}: MultiValuePickerProps) {
  const addValue = (nextValue: string) => {
    if (!nextValue) return;
    if (values.includes(nextValue)) return;
    onChange([...values, nextValue]);
  };

  const removeValue = (target: string) => {
    onChange(values.filter((value) => value !== target));
  };

  const clear = () => onChange([]);

  return (
    <div className="space-y-1">
      <select
        value=""
        onChange={(event) => addValue(event.target.value)}
        className={className || "bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => {
          const isSelected = values.includes(option.value);
          return (
            <option
              key={option.value}
              value={option.value}
              disabled={option.disabled || isSelected}
            >
              {option.label}{isSelected ? " (selected)" : ""}
            </option>
          );
        })}
      </select>
      {values.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {values.map((value) => {
            const label = options.find((option) => option.value === value)?.label || value;
            return (
              <button
                key={value}
                onClick={() => removeValue(value)}
                className="px-2 py-0.5 text-xs bg-background border border-card-border rounded text-muted hover:text-red"
                title="Remove"
              >
                {label} x
              </button>
            );
          })}
          <button
            onClick={clear}
            className="px-2 py-0.5 text-xs border border-red/30 rounded text-red hover:bg-red/10"
          >
            Clear
          </button>
        </div>
      )}
    </div>
  );
}
