import type { ModelAllowed } from "../api";
import { price } from "../format";
import { Panel } from "./elements";

/** The models the claim agent may use, set in data/models.json: read only. */
export function ModelsAllowed({
  models,
}: Readonly<{ models: ModelAllowed[] }>) {
  return (
    <Panel title="Models the claim agent may use">
      <p className="muted">
        Set in data/models.json and can&apos;t be changed here. Prices are in US
        dollars per million tokens.
      </p>
      <div className="table-scroll">
        <table className="data-table" aria-label="Models allowed">
          <thead>
            <tr>
              <th scope="col">Model</th>
              <th scope="col">Reasoning efforts</th>
              <th scope="col" className="numeric">
                Input
              </th>
              <th scope="col" className="numeric">
                Output
              </th>
            </tr>
          </thead>
          <tbody>
            {models.map((model) => (
              <tr key={model.model}>
                <td>
                  {model.label}
                  <span className="muted mono"> {model.model}</span>
                </td>
                <td>{model.reasoning_efforts.join(", ")}</td>
                <td className="numeric">{price(model.input_price)}</td>
                <td className="numeric">{price(model.output_price)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
