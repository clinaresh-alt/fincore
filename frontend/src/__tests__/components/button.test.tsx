/**
 * Tests para el componente Button
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Button, buttonVariants } from "@/components/ui/button";

describe("Button Component", () => {
  describe("Renderizado basico", () => {
    it("renderiza el boton con texto", () => {
      render(<Button>Click me</Button>);
      expect(screen.getByRole("button", { name: /click me/i })).toBeInTheDocument();
    });

    it("renderiza como elemento button por defecto", () => {
      render(<Button>Test</Button>);
      const button = screen.getByRole("button");
      expect(button.tagName).toBe("BUTTON");
    });

    it("aplica className adicional", () => {
      render(<Button className="custom-class">Test</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveClass("custom-class");
    });
  });

  describe("Variantes", () => {
    it("aplica variante default correctamente", () => {
      render(<Button variant="default">Default</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveClass("bg-primary");
    });

    it("aplica variante destructive", () => {
      render(<Button variant="destructive">Delete</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveClass("bg-destructive");
    });

    it("aplica variante outline", () => {
      render(<Button variant="outline">Outline</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveClass("border");
    });

    it("aplica variante secondary", () => {
      render(<Button variant="secondary">Secondary</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveClass("bg-secondary");
    });

    it("aplica variante ghost", () => {
      render(<Button variant="ghost">Ghost</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveClass("hover:bg-accent");
    });

    it("aplica variante link", () => {
      render(<Button variant="link">Link</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveClass("underline-offset-4");
    });

    it("aplica variante success", () => {
      render(<Button variant="success">Success</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveClass("bg-green-600");
    });
  });

  describe("Tamanos", () => {
    it("aplica tamano default", () => {
      render(<Button size="default">Default</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveClass("h-10");
    });

    it("aplica tamano sm", () => {
      render(<Button size="sm">Small</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveClass("h-9");
    });

    it("aplica tamano lg", () => {
      render(<Button size="lg">Large</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveClass("h-11");
    });

    it("aplica tamano icon", () => {
      render(<Button size="icon">I</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveClass("h-10");
      expect(button).toHaveClass("w-10");
    });
  });

  describe("Estado disabled", () => {
    it("puede ser deshabilitado", () => {
      render(<Button disabled>Disabled</Button>);
      const button = screen.getByRole("button");
      expect(button).toBeDisabled();
    });

    it("aplica estilos de disabled", () => {
      render(<Button disabled>Disabled</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveClass("disabled:opacity-50");
    });
  });

  describe("Estado loading", () => {
    it("muestra spinner cuando loading es true", () => {
      render(<Button loading>Submit</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveTextContent("Cargando...");
    });

    it("deshabilita el boton cuando loading", () => {
      render(<Button loading>Submit</Button>);
      const button = screen.getByRole("button");
      expect(button).toBeDisabled();
    });

    it("muestra SVG de spinner", () => {
      render(<Button loading>Submit</Button>);
      const spinner = document.querySelector("svg.animate-spin");
      expect(spinner).toBeInTheDocument();
    });
  });

  describe("Eventos", () => {
    it("ejecuta onClick cuando se hace click", () => {
      const handleClick = vi.fn();
      render(<Button onClick={handleClick}>Click</Button>);

      fireEvent.click(screen.getByRole("button"));
      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it("no ejecuta onClick cuando disabled", () => {
      const handleClick = vi.fn();
      render(
        <Button onClick={handleClick} disabled>
          Click
        </Button>
      );

      fireEvent.click(screen.getByRole("button"));
      expect(handleClick).not.toHaveBeenCalled();
    });

    it("no ejecuta onClick cuando loading", () => {
      const handleClick = vi.fn();
      render(
        <Button onClick={handleClick} loading>
          Click
        </Button>
      );

      fireEvent.click(screen.getByRole("button"));
      expect(handleClick).not.toHaveBeenCalled();
    });
  });

  describe("Accesibilidad", () => {
    it("tiene role button", () => {
      render(<Button>Test</Button>);
      expect(screen.getByRole("button")).toBeInTheDocument();
    });

    it("puede tener aria-label", () => {
      render(<Button aria-label="Close dialog">X</Button>);
      expect(screen.getByLabelText("Close dialog")).toBeInTheDocument();
    });

    it("soporta type submit", () => {
      render(<Button type="submit">Submit</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveAttribute("type", "submit");
    });
  });

  describe("asChild prop", () => {
    it("renderiza hijo cuando asChild es true", () => {
      render(
        <Button asChild>
          <a href="/test">Link Button</a>
        </Button>
      );
      const link = screen.getByRole("link", { name: /link button/i });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute("href", "/test");
    });
  });
});

describe("buttonVariants", () => {
  it("genera clases para variante default", () => {
    const classes = buttonVariants({ variant: "default" });
    expect(classes).toContain("bg-primary");
  });

  it("genera clases para tamano lg", () => {
    const classes = buttonVariants({ size: "lg" });
    expect(classes).toContain("h-11");
  });

  it("combina variante y tamano", () => {
    const classes = buttonVariants({ variant: "destructive", size: "sm" });
    expect(classes).toContain("bg-destructive");
    expect(classes).toContain("h-9");
  });

  it("usa defaults cuando no se especifica", () => {
    const classes = buttonVariants({});
    expect(classes).toContain("bg-primary");
    expect(classes).toContain("h-10");
  });
});
