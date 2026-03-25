/**
 * Tests para componentes Card
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";

describe("Card Component", () => {
  it("renderiza Card basico", () => {
    render(<Card data-testid="card">Content</Card>);
    expect(screen.getByTestId("card")).toBeInTheDocument();
  });

  it("aplica clases de estilo base", () => {
    render(<Card data-testid="card">Content</Card>);
    const card = screen.getByTestId("card");
    expect(card).toHaveClass("rounded-lg");
    expect(card).toHaveClass("border");
  });

  it("acepta className adicional", () => {
    render(
      <Card data-testid="card" className="custom-class">
        Content
      </Card>
    );
    const card = screen.getByTestId("card");
    expect(card).toHaveClass("custom-class");
  });

  it("renderiza contenido children", () => {
    render(<Card>Card Content</Card>);
    expect(screen.getByText("Card Content")).toBeInTheDocument();
  });
});

describe("CardHeader Component", () => {
  it("renderiza CardHeader", () => {
    render(<CardHeader data-testid="header">Header</CardHeader>);
    expect(screen.getByTestId("header")).toBeInTheDocument();
  });

  it("aplica estilos de padding", () => {
    render(<CardHeader data-testid="header">Header</CardHeader>);
    const header = screen.getByTestId("header");
    expect(header).toHaveClass("p-6");
  });

  it("acepta className adicional", () => {
    render(
      <CardHeader data-testid="header" className="extra-class">
        Header
      </CardHeader>
    );
    expect(screen.getByTestId("header")).toHaveClass("extra-class");
  });
});

describe("CardTitle Component", () => {
  it("renderiza CardTitle", () => {
    render(<CardTitle>Mi Titulo</CardTitle>);
    expect(screen.getByText("Mi Titulo")).toBeInTheDocument();
  });

  it("aplica estilos de tipografia", () => {
    render(<CardTitle data-testid="title">Titulo</CardTitle>);
    const title = screen.getByTestId("title");
    expect(title).toHaveClass("text-2xl");
    expect(title).toHaveClass("font-semibold");
  });

  it("acepta className adicional", () => {
    render(
      <CardTitle data-testid="title" className="text-red-500">
        Titulo
      </CardTitle>
    );
    expect(screen.getByTestId("title")).toHaveClass("text-red-500");
  });
});

describe("CardDescription Component", () => {
  it("renderiza CardDescription", () => {
    render(<CardDescription>Descripcion del card</CardDescription>);
    expect(screen.getByText("Descripcion del card")).toBeInTheDocument();
  });

  it("aplica estilos de texto muted", () => {
    render(<CardDescription data-testid="desc">Descripcion</CardDescription>);
    const desc = screen.getByTestId("desc");
    expect(desc).toHaveClass("text-sm");
    expect(desc).toHaveClass("text-muted-foreground");
  });
});

describe("CardContent Component", () => {
  it("renderiza CardContent", () => {
    render(<CardContent data-testid="content">Contenido</CardContent>);
    expect(screen.getByTestId("content")).toBeInTheDocument();
  });

  it("aplica padding", () => {
    render(<CardContent data-testid="content">Contenido</CardContent>);
    const content = screen.getByTestId("content");
    expect(content).toHaveClass("p-6");
    expect(content).toHaveClass("pt-0");
  });
});

describe("CardFooter Component", () => {
  it("renderiza CardFooter", () => {
    render(<CardFooter data-testid="footer">Footer</CardFooter>);
    expect(screen.getByTestId("footer")).toBeInTheDocument();
  });

  it("aplica estilos flex", () => {
    render(<CardFooter data-testid="footer">Footer</CardFooter>);
    const footer = screen.getByTestId("footer");
    expect(footer).toHaveClass("flex");
    expect(footer).toHaveClass("items-center");
  });
});

describe("Card Composicion Completa", () => {
  it("renderiza Card con todos los subcomponentes", () => {
    render(
      <Card data-testid="card">
        <CardHeader>
          <CardTitle>Titulo</CardTitle>
          <CardDescription>Descripcion</CardDescription>
        </CardHeader>
        <CardContent>
          <p>Contenido principal</p>
        </CardContent>
        <CardFooter>
          <span>Footer info</span>
        </CardFooter>
      </Card>
    );

    expect(screen.getByTestId("card")).toBeInTheDocument();
    expect(screen.getByText("Titulo")).toBeInTheDocument();
    expect(screen.getByText("Descripcion")).toBeInTheDocument();
    expect(screen.getByText("Contenido principal")).toBeInTheDocument();
    expect(screen.getByText("Footer info")).toBeInTheDocument();
  });

  it("mantiene estructura semantica correcta", () => {
    render(
      <Card data-testid="card">
        <CardHeader data-testid="header">
          <CardTitle data-testid="title">Test</CardTitle>
        </CardHeader>
        <CardContent data-testid="content">Content</CardContent>
      </Card>
    );

    const card = screen.getByTestId("card");
    const header = screen.getByTestId("header");
    const title = screen.getByTestId("title");
    const content = screen.getByTestId("content");

    // Verificar que header y content son hijos de card
    expect(card).toContainElement(header);
    expect(card).toContainElement(content);
    expect(header).toContainElement(title);
  });
});
