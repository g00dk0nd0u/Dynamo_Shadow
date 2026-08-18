using System.Xml.Linq;
using Xunit;

namespace RevitShadow.Tests;

public sealed class RevitShadowAddinManifestTests
{
    [Fact]
    public void DevelopmentCommandTemplateHasStableRevitContract()
    {
        var templatePath = Path.Combine(AppContext.BaseDirectory, "RevitShadow.addin.template");
        var addIn = XDocument.Load(templatePath).Root?.Element("AddIn");

        Assert.NotNull(addIn);
        Assert.Equal("Command", (string?)addIn.Attribute("Type"));
        Assert.Equal("Dynamo Shadow Project Context Smoke Test", (string?)addIn.Element("Text"));
        Assert.Equal("RevitShadow.ForwardProjectContextSmokeCommand", (string?)addIn.Element("FullClassName"));
        Assert.Equal("__REVIT_SHADOW_ASSEMBLY__", (string?)addIn.Element("Assembly"));
        Assert.Equal("F39416B1-9B93-4E7C-AC9B-3855E524670C", (string?)addIn.Element("AddInId"));
        Assert.Equal("DYSH", (string?)addIn.Element("VendorId"));
    }
}
